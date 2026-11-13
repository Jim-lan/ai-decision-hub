"""Add prepared context policy and conservative budget ledgers."""

from alembic import op


revision = "0007_context_budget"
down_revision = "0006_identity_constraints"


def upgrade():
    op.execute("""
        ALTER TABLE runs
            ADD COLUMN request_schema_version SMALLINT,
            ADD COLUMN normalized_request JSONB,
            ADD COLUMN max_cost_microusd BIGINT;
        UPDATE runs SET request_schema_version=0;
        ALTER TABLE runs
            ALTER COLUMN request_schema_version SET DEFAULT 0,
            ALTER COLUMN request_schema_version SET NOT NULL,
            ADD CONSTRAINT runs_request_schema
                CHECK (
                    (request_schema_version=0 AND normalized_request IS NULL)
                    OR (request_schema_version=1 AND normalized_request IS NOT NULL
                        AND jsonb_typeof(normalized_request)='object')
                ),
            ADD CONSTRAINT runs_max_cost_nonnegative
                CHECK (max_cost_microusd IS NULL OR max_cost_microusd >= 0);

        CREATE TABLE run_context_sources (
            run_id UUID NOT NULL REFERENCES runs(run_id),
            position SMALLINT NOT NULL CHECK (position BETWEEN 1 AND 32),
            message_id UUID NOT NULL REFERENCES messages(message_id),
            PRIMARY KEY (run_id, position),
            UNIQUE (run_id, message_id)
        );

        CREATE FUNCTION validate_run_context_source() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM runs r
                JOIN messages m ON m.message_id=NEW.message_id
                JOIN conversations c ON c.conversation_id=m.conversation_id
                WHERE r.run_id=NEW.run_id AND r.project_id=c.project_id
            ) THEN
                RAISE EXCEPTION 'Run context source must belong to the run project';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER run_context_sources_scope
            BEFORE INSERT OR UPDATE ON run_context_sources
            FOR EACH ROW EXECUTE FUNCTION validate_run_context_source();
        CREATE TRIGGER run_context_sources_immutable
            BEFORE UPDATE OR DELETE ON run_context_sources
            FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();
        CREATE TRIGGER run_context_sources_no_truncate
            BEFORE TRUNCATE ON run_context_sources
            FOR EACH STATEMENT EXECUTE FUNCTION reject_evidence_change();

        CREATE TABLE project_provider_policies (
            project_id UUID NOT NULL REFERENCES projects(project_id),
            provider_id TEXT NOT NULL,
            alias TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('allowed','blocked')),
            consented_at TIMESTAMPTZ,
            verified_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            max_input_tokens BIGINT NOT NULL CHECK (max_input_tokens > 0),
            PRIMARY KEY (project_id, provider_id, alias),
            FOREIGN KEY (provider_id, alias) REFERENCES provider_models(provider_id, alias),
            CHECK (char_length(policy_version) BETWEEN 1 AND 160
                   AND policy_version ~ '[^[:space:]]'),
            CHECK (expires_at > verified_at),
            CHECK (status='blocked' OR consented_at IS NOT NULL),
            CHECK (consented_at IS NULL OR consented_at < expires_at)
        );

        CREATE TABLE context_source_rules (
            project_id UUID NOT NULL REFERENCES projects(project_id),
            message_id UUID NOT NULL REFERENCES messages(message_id),
            provider_id TEXT NOT NULL,
            alias TEXT NOT NULL,
            decision TEXT NOT NULL CHECK (decision IN ('allow','deny','redact')),
            redacted_content TEXT,
            policy_version TEXT NOT NULL,
            PRIMARY KEY (message_id, provider_id, alias),
            FOREIGN KEY (provider_id, alias) REFERENCES provider_models(provider_id, alias),
            CHECK (char_length(policy_version) BETWEEN 1 AND 160
                   AND policy_version ~ '[^[:space:]]'),
            CHECK (
                (decision='redact' AND redacted_content IS NOT NULL
                 AND redacted_content ~ '[^[:space:]]')
                OR (decision<>'redact' AND redacted_content IS NULL)
            )
        );

        CREATE FUNCTION validate_context_source_rule() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM messages m JOIN conversations c USING (conversation_id)
                WHERE m.message_id=NEW.message_id AND c.project_id=NEW.project_id
            ) THEN
                RAISE EXCEPTION 'Context source policy must match the message project';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER context_source_rules_scope
            BEFORE INSERT OR UPDATE ON context_source_rules
            FOR EACH ROW EXECUTE FUNCTION validate_context_source_rule();

        CREATE FUNCTION uuid_array_is_unique(values_to_check UUID[])
        RETURNS BOOLEAN LANGUAGE sql IMMUTABLE AS $$
            SELECT cardinality(values_to_check) = count(DISTINCT value)
              FROM unnest(values_to_check) AS item(value);
        $$;

        CREATE TABLE prepared_contexts (
            candidate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID NOT NULL REFERENCES runs(run_id),
            target_id UUID NOT NULL UNIQUE REFERENCES run_targets(target_id),
            project_id UUID NOT NULL REFERENCES projects(project_id),
            policy_version TEXT NOT NULL,
            selected_source_message_ids UUID[] NOT NULL DEFAULT '{}',
            source_message_ids UUID[] NOT NULL DEFAULT '{}',
            model_visible_input TEXT NOT NULL,
            request_hash TEXT NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
            redaction_count INTEGER NOT NULL CHECK (redaction_count >= 0),
            omission_count INTEGER NOT NULL CHECK (omission_count >= 0),
            input_token_limit BIGINT NOT NULL CHECK (input_token_limit > 0),
            input_token_bound BIGINT NOT NULL CHECK (input_token_bound >= 0),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (run_id, target_id),
            CHECK (char_length(policy_version) BETWEEN 1 AND 160
                   AND policy_version ~ '[^[:space:]]'),
            CHECK (request_hash=encode(sha256(convert_to(model_visible_input,'UTF8')),'hex')),
            CHECK (input_token_bound=octet_length(model_visible_input)
                   AND input_token_bound<=input_token_limit),
            CHECK (cardinality(selected_source_message_ids) <= 32
                   AND uuid_array_is_unique(selected_source_message_ids)),
            CHECK (cardinality(source_message_ids) <= 32
                   AND uuid_array_is_unique(source_message_ids)
                   AND source_message_ids <@ selected_source_message_ids)
        );

        CREATE FUNCTION validate_prepared_context() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM runs r JOIN run_targets t ON t.run_id=r.run_id
                JOIN project_provider_policies pp
                  ON pp.project_id=r.project_id AND pp.provider_id=t.provider
                 AND pp.alias=t.alias
                WHERE r.run_id=NEW.run_id AND t.target_id=NEW.target_id
                  AND r.project_id=NEW.project_id
                  AND pp.policy_version=NEW.policy_version
            ) THEN
                RAISE EXCEPTION 'Prepared context must match its run target and project';
            END IF;
            IF EXISTS (
                SELECT 1 FROM unnest(NEW.selected_source_message_ids) source_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM run_context_sources selected
                    WHERE selected.run_id=NEW.run_id
                      AND selected.message_id=source_id
                )
            ) THEN
                RAISE EXCEPTION 'Prepared context source was not selected for the run';
            END IF;
            IF NEW.selected_source_message_ids IS DISTINCT FROM ARRAY(
                SELECT selected.message_id FROM run_context_sources selected
                WHERE selected.run_id=NEW.run_id ORDER BY selected.position
            ) THEN
                RAISE EXCEPTION 'Prepared context must preserve the selected source order';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER prepared_contexts_scope
            BEFORE INSERT OR UPDATE ON prepared_contexts
            FOR EACH ROW EXECUTE FUNCTION validate_prepared_context();
        CREATE TRIGGER prepared_contexts_immutable
            BEFORE UPDATE OR DELETE ON prepared_contexts
            FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();
        CREATE TRIGGER prepared_contexts_no_truncate
            BEFORE TRUNCATE ON prepared_contexts
            FOR EACH STATEMENT EXECUTE FUNCTION reject_evidence_change();

        CREATE TABLE owner_budget_policies (
            owner_id UUID PRIMARY KEY REFERENCES users(user_id),
            policy_version TEXT NOT NULL,
            run_cap_microusd BIGINT NOT NULL DEFAULT 0 CHECK (run_cap_microusd >= 0),
            day_cap_microusd BIGINT NOT NULL DEFAULT 0 CHECK (day_cap_microusd >= 0),
            month_cap_microusd BIGINT NOT NULL DEFAULT 0 CHECK (month_cap_microusd >= 0),
            effective_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ,
            CHECK (char_length(policy_version) BETWEEN 1 AND 160
                   AND policy_version ~ '[^[:space:]]'),
            CHECK (expires_at IS NULL OR expires_at > effective_at)
        );

        CREATE TABLE provider_budget_policies (
            provider_id TEXT NOT NULL,
            alias TEXT NOT NULL,
            quota_account_id TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            pricing_version TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('active','disabled')),
            verified_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            quota_timezone TEXT NOT NULL,
            fixed_cost_microusd BIGINT NOT NULL CHECK (fixed_cost_microusd >= 0),
            input_microusd_per_million BIGINT NOT NULL CHECK (input_microusd_per_million >= 0),
            output_microusd_per_million BIGINT NOT NULL CHECK (output_microusd_per_million >= 0),
            max_input_tokens BIGINT NOT NULL CHECK (max_input_tokens > 0),
            max_output_tokens BIGINT NOT NULL CHECK (max_output_tokens > 0),
            daily_call_cap BIGINT NOT NULL CHECK (daily_call_cap >= 0),
            daily_input_token_cap BIGINT NOT NULL CHECK (daily_input_token_cap >= 0),
            daily_output_token_cap BIGINT NOT NULL CHECK (daily_output_token_cap >= 0),
            PRIMARY KEY (provider_id, alias),
            FOREIGN KEY (provider_id, alias) REFERENCES provider_models(provider_id, alias),
            CHECK (expires_at > verified_at),
            CHECK (char_length(quota_account_id) BETWEEN 1 AND 160
                   AND quota_account_id ~ '[^[:space:]]'),
            CHECK (char_length(policy_version) BETWEEN 1 AND 160
                   AND policy_version ~ '[^[:space:]]'),
            CHECK (char_length(pricing_version) BETWEEN 1 AND 160
                   AND pricing_version ~ '[^[:space:]]'),
            CHECK (char_length(quota_timezone) BETWEEN 1 AND 160
                   AND quota_timezone ~ '[^[:space:]]')
        );
        CREATE FUNCTION validate_shared_quota_policy() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            new_lock BIGINT;
            old_lock BIGINT;
        BEGIN
            new_lock := hashtextextended(
                'quota-policy:' || NEW.provider_id || ':' || NEW.quota_account_id, 0
            );
            IF TG_OP='UPDATE' THEN
                old_lock := hashtextextended(
                    'quota-policy:' || OLD.provider_id || ':' || OLD.quota_account_id, 0
                );
                PERFORM pg_advisory_xact_lock(least(new_lock,old_lock));
                IF new_lock<>old_lock THEN
                    PERFORM pg_advisory_xact_lock(greatest(new_lock,old_lock));
                END IF;
            ELSE
                PERFORM pg_advisory_xact_lock(new_lock);
            END IF;
            IF EXISTS (
                SELECT 1 FROM provider_budget_policies other
                WHERE other.provider_id=NEW.provider_id
                  AND other.quota_account_id=NEW.quota_account_id
                  AND (other.provider_id,other.alias)<>(NEW.provider_id,NEW.alias)
                  AND ROW(
                      other.quota_timezone,other.daily_call_cap,
                      other.daily_input_token_cap,other.daily_output_token_cap
                  ) IS DISTINCT FROM ROW(
                      NEW.quota_timezone,NEW.daily_call_cap,
                      NEW.daily_input_token_cap,NEW.daily_output_token_cap
                  )
            ) THEN
                RAISE EXCEPTION 'Aliases sharing a quota account must use one quota policy';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER provider_budget_policies_shared_scope
            BEFORE INSERT OR UPDATE ON provider_budget_policies
            FOR EACH ROW EXECUTE FUNCTION validate_shared_quota_policy();

        CREATE TABLE budget_reservations (
            reservation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_id UUID NOT NULL REFERENCES users(user_id),
            project_id UUID NOT NULL REFERENCES projects(project_id),
            run_id UUID NOT NULL REFERENCES runs(run_id),
            target_id UUID NOT NULL UNIQUE REFERENCES run_targets(target_id),
            provider_id TEXT NOT NULL,
            alias TEXT NOT NULL,
            quota_account_id TEXT NOT NULL,
            reservation_key TEXT NOT NULL,
            owner_policy_version TEXT NOT NULL,
            provider_policy_version TEXT NOT NULL,
            pricing_version TEXT NOT NULL,
            owner_day DATE NOT NULL,
            owner_month DATE NOT NULL,
            provider_day DATE NOT NULL,
            amount_microusd BIGINT NOT NULL CHECK (amount_microusd >= 0),
            input_token_bound BIGINT NOT NULL CHECK (input_token_bound >= 0),
            output_token_bound BIGINT NOT NULL CHECK (output_token_bound >= 0),
            requested_run_cap_microusd BIGINT CHECK (requested_run_cap_microusd >= 0),
            state TEXT NOT NULL CHECK (state IN ('reserved','held','settled','released')),
            actual_cost_microusd BIGINT CHECK (actual_cost_microusd >= 0),
            input_tokens BIGINT CHECK (input_tokens >= 0),
            output_tokens BIGINT CHECK (output_tokens >= 0),
            dispatch_validated_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (owner_id, reservation_key),
            FOREIGN KEY (provider_id, alias) REFERENCES provider_models(provider_id, alias),
            CHECK (char_length(reservation_key) BETWEEN 1 AND 160
                   AND reservation_key ~ '[^[:space:]]'),
            CHECK (state<>'settled' OR actual_cost_microusd IS NOT NULL),
            CHECK (state NOT IN ('reserved','released') OR actual_cost_microusd IS NULL)
        );
        CREATE INDEX budget_reservations_owner_period
            ON budget_reservations(owner_id, owner_day, owner_month, state);
        CREATE INDEX budget_reservations_provider_period
            ON budget_reservations(provider_id, quota_account_id, provider_day, state);

        CREATE FUNCTION validate_budget_reservation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM runs r JOIN run_targets t ON t.run_id=r.run_id
                WHERE r.run_id=NEW.run_id AND t.target_id=NEW.target_id
                  AND r.owner_id=NEW.owner_id AND r.project_id=NEW.project_id
                  AND t.provider=NEW.provider_id AND t.alias=NEW.alias
                  AND r.max_cost_microusd IS NOT DISTINCT FROM
                      NEW.requested_run_cap_microusd
            ) THEN
                RAISE EXCEPTION 'Budget reservation must match its owned run target';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER budget_reservations_scope
            BEFORE INSERT OR UPDATE ON budget_reservations
            FOR EACH ROW EXECUTE FUNCTION validate_budget_reservation();

        CREATE FUNCTION protect_budget_reservation_identity() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP='DELETE' OR ROW(
                OLD.reservation_id, OLD.owner_id, OLD.project_id, OLD.run_id, OLD.target_id,
                OLD.provider_id, OLD.alias, OLD.quota_account_id, OLD.reservation_key,
                OLD.owner_policy_version, OLD.provider_policy_version, OLD.pricing_version,
                OLD.amount_microusd, OLD.input_token_bound, OLD.output_token_bound,
                OLD.requested_run_cap_microusd, OLD.created_at
            ) IS DISTINCT FROM ROW(
                NEW.reservation_id, NEW.owner_id, NEW.project_id, NEW.run_id, NEW.target_id,
                NEW.provider_id, NEW.alias, NEW.quota_account_id, NEW.reservation_key,
                NEW.owner_policy_version, NEW.provider_policy_version, NEW.pricing_version,
                NEW.amount_microusd, NEW.input_token_bound, NEW.output_token_bound,
                NEW.requested_run_cap_microusd, NEW.created_at
            ) THEN
                RAISE EXCEPTION 'Budget reservation identity and bounds are immutable';
            END IF;
            NEW.updated_at := now();
            RETURN NEW;
        END; $$;
        CREATE TRIGGER budget_reservations_identity
            BEFORE UPDATE OR DELETE ON budget_reservations
            FOR EACH ROW EXECUTE FUNCTION protect_budget_reservation_identity();
        CREATE TRIGGER budget_reservations_no_truncate
            BEFORE TRUNCATE ON budget_reservations
            FOR EACH STATEMENT EXECUTE FUNCTION reject_evidence_change();

        CREATE TABLE dispatch_grants (
            grant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            reservation_id UUID NOT NULL REFERENCES budget_reservations(reservation_id),
            candidate_id UUID NOT NULL REFERENCES prepared_contexts(candidate_id),
            attempt_id UUID NOT NULL UNIQUE,
            owner_id UUID NOT NULL REFERENCES users(user_id),
            project_id UUID NOT NULL REFERENCES projects(project_id),
            run_id UUID NOT NULL REFERENCES runs(run_id),
            target_id UUID NOT NULL REFERENCES run_targets(target_id),
            provider_id TEXT NOT NULL,
            alias TEXT NOT NULL,
            requested_model_id TEXT NOT NULL,
            input_digest TEXT NOT NULL CHECK (input_digest ~ '^[0-9a-f]{64}$'),
            input_token_bound BIGINT NOT NULL CHECK (input_token_bound >= 0),
            output_token_bound BIGINT NOT NULL CHECK (output_token_bound >= 0),
            deadline TIMESTAMPTZ NOT NULL,
            validated_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (reservation_id),
            FOREIGN KEY (provider_id, alias) REFERENCES provider_models(provider_id, alias),
            CHECK (deadline > validated_at),
            CHECK (char_length(requested_model_id) BETWEEN 1 AND 160
                   AND requested_model_id ~ '[^[:space:]]')
        );

        CREATE FUNCTION validate_dispatch_grant() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM budget_reservations b
                JOIN prepared_contexts c
                  ON c.target_id=b.target_id AND c.run_id=b.run_id
                JOIN runs r ON r.run_id=b.run_id
                JOIN run_targets t ON t.target_id=b.target_id
                WHERE b.reservation_id=NEW.reservation_id
                  AND c.candidate_id=NEW.candidate_id
                  AND b.owner_id=NEW.owner_id AND b.project_id=NEW.project_id
                  AND b.run_id=NEW.run_id AND b.target_id=NEW.target_id
                  AND b.provider_id=NEW.provider_id AND b.alias=NEW.alias
                  AND t.model_id=NEW.requested_model_id
                  AND c.request_hash=NEW.input_digest
                  AND c.input_token_bound=NEW.input_token_bound
                  AND b.output_token_bound=NEW.output_token_bound
                  AND r.deadline=NEW.deadline
                  AND b.state='reserved'
            ) THEN
                RAISE EXCEPTION 'Dispatch grant must match a current reservation and context';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER dispatch_grants_scope
            BEFORE INSERT OR UPDATE ON dispatch_grants
            FOR EACH ROW EXECUTE FUNCTION validate_dispatch_grant();
        CREATE TRIGGER dispatch_grants_immutable
            BEFORE UPDATE OR DELETE ON dispatch_grants
            FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();
        CREATE TRIGGER dispatch_grants_no_truncate
            BEFORE TRUNCATE ON dispatch_grants
            FOR EACH STATEMENT EXECUTE FUNCTION reject_evidence_change();

        CREATE TABLE dispatch_claims (
            claim_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            grant_id UUID NOT NULL UNIQUE REFERENCES dispatch_grants(grant_id),
            attempt_id UUID NOT NULL UNIQUE,
            claimed_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE FUNCTION validate_dispatch_claim() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM dispatch_grants g
                WHERE g.grant_id=NEW.grant_id AND g.attempt_id=NEW.attempt_id
                  AND NEW.claimed_at>=g.validated_at AND NEW.claimed_at<g.deadline
            ) THEN
                RAISE EXCEPTION 'Dispatch claim must match a current grant';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER dispatch_claims_scope
            BEFORE INSERT OR UPDATE ON dispatch_claims
            FOR EACH ROW EXECUTE FUNCTION validate_dispatch_claim();
        CREATE TRIGGER dispatch_claims_immutable
            BEFORE UPDATE OR DELETE ON dispatch_claims
            FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();
        CREATE TRIGGER dispatch_claims_no_truncate
            BEFORE TRUNCATE ON dispatch_claims
            FOR EACH STATEMENT EXECUTE FUNCTION reject_evidence_change();

        CREATE TABLE usage_events (
            entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            reservation_id UUID NOT NULL REFERENCES budget_reservations(reservation_id),
            run_id UUID NOT NULL REFERENCES runs(run_id),
            target_id UUID NOT NULL REFERENCES run_targets(target_id),
            attempt_id UUID,
            kind TEXT NOT NULL CHECK (kind IN ('reserve','release','settle','hold')),
            amount_microusd BIGINT NOT NULL CHECK (amount_microusd >= 0),
            input_tokens BIGINT CHECK (input_tokens >= 0),
            output_tokens BIGINT CHECK (output_tokens >= 0),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (reservation_id, kind)
        );
        CREATE FUNCTION validate_usage_event() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM budget_reservations b
                WHERE b.reservation_id=NEW.reservation_id
                  AND b.run_id=NEW.run_id AND b.target_id=NEW.target_id
            ) OR (
                NEW.attempt_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM dispatch_grants g
                    WHERE g.reservation_id=NEW.reservation_id
                      AND g.attempt_id=NEW.attempt_id
                )
            ) THEN
                RAISE EXCEPTION 'Usage evidence must match its reservation and attempt';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER usage_events_scope
            BEFORE INSERT OR UPDATE ON usage_events
            FOR EACH ROW EXECUTE FUNCTION validate_usage_event();
        CREATE TRIGGER usage_events_immutable
            BEFORE UPDATE OR DELETE ON usage_events
            FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();
        CREATE TRIGGER usage_events_no_truncate
            BEFORE TRUNCATE ON usage_events
            FOR EACH STATEMENT EXECUTE FUNCTION reject_evidence_change();
    """)


def downgrade():
    raise RuntimeError("Restore the verified pre-migration backup to roll back.")
