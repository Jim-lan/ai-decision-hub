"""Add canonical run lifecycle, ordered events, fenced work, and attempts."""

from alembic import op


revision = "0008_run_lifecycle"
down_revision = "0007_context_budget"


def upgrade():
    op.execute(
        """
        ALTER TABLE runs
            ADD COLUMN state TEXT,
            ADD COLUMN revision BIGINT NOT NULL DEFAULT 1,
            ADD COLUMN error_code TEXT,
            ADD COLUMN comparison_id UUID,
            ADD COLUMN terminal_at TIMESTAMPTZ;

        ALTER TABLE run_targets
            ADD COLUMN state TEXT,
            ADD COLUMN attempt_no INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN error_code TEXT,
            ADD COLUMN context_snapshot_id UUID REFERENCES prepared_contexts(candidate_id);

        UPDATE run_targets target
           SET state = CASE
               WHEN EXISTS (
                   SELECT 1 FROM model_responses response
                    WHERE response.target_id=target.target_id
               ) THEN 'succeeded'
               WHEN EXISTS (
                   SELECT 1 FROM runs run
                    WHERE run.run_id=target.run_id AND run.deadline<=now()
               ) THEN 'timed_out'
               WHEN target.acquisition_mode='manual' THEN 'awaiting_manual'
               ELSE 'pending'
           END,
               error_code = CASE
                   WHEN NOT EXISTS (
                       SELECT 1 FROM model_responses response
                        WHERE response.target_id=target.target_id
                   ) AND EXISTS (
                       SELECT 1 FROM runs run
                        WHERE run.run_id=target.run_id AND run.deadline<=now()
                   ) THEN 'timeout'
                   ELSE NULL
               END;

        UPDATE runs run
           SET state = CASE
               WHEN run.deadline<=now() AND NOT EXISTS (
                   SELECT 1 FROM run_targets target
                   JOIN model_responses response USING (target_id)
                   WHERE target.run_id=run.run_id
               ) THEN 'failed'
               WHEN run.deadline<=now() OR NOT EXISTS (
                   SELECT 1 FROM run_targets target
                   WHERE target.run_id=run.run_id AND target.state<>'succeeded'
               ) THEN 'synthesizing'
               WHEN EXISTS (
                   SELECT 1 FROM run_targets target
                   WHERE target.run_id=run.run_id AND target.state='awaiting_manual'
               ) AND NOT EXISTS (
                   SELECT 1 FROM run_targets target
                   WHERE target.run_id=run.run_id AND target.state='pending'
               ) THEN 'awaiting_manual'
               ELSE 'queued'
           END,
               error_code = CASE
                   WHEN run.deadline<=now() AND NOT EXISTS (
                       SELECT 1 FROM run_targets target
                       JOIN model_responses response USING (target_id)
                       WHERE target.run_id=run.run_id
                   ) THEN 'timeout'
                   ELSE NULL
               END,
               terminal_at = CASE
                   WHEN run.deadline<=now() AND NOT EXISTS (
                       SELECT 1 FROM run_targets target
                       JOIN model_responses response USING (target_id)
                       WHERE target.run_id=run.run_id
                   ) THEN now()
                   ELSE NULL
               END;

        ALTER TABLE runs
            ALTER COLUMN state SET DEFAULT 'queued',
            ALTER COLUMN state SET NOT NULL,
            ADD CONSTRAINT runs_state CHECK (state IN (
                'queued','running','awaiting_manual','synthesizing',
                'completed','completed_partial','failed','cancelled'
            )),
            ADD CONSTRAINT runs_revision_positive CHECK (revision > 0),
            ADD CONSTRAINT runs_error_code CHECK (error_code IS NULL OR error_code IN (
                'disabled','policy_denied','budget_denied','quota_denied','timeout',
                'cancelled','provider_error','delivery_unknown','invalid_response',
                'internal_error'
            )),
            ADD CONSTRAINT runs_terminal_shape CHECK (
                (state IN ('completed','completed_partial','failed','cancelled'))
                = (terminal_at IS NOT NULL)
            );

        ALTER TABLE run_targets
            ALTER COLUMN state SET DEFAULT 'pending',
            ALTER COLUMN state SET NOT NULL,
            ADD CONSTRAINT run_targets_state CHECK (state IN (
                'pending','in_flight','awaiting_manual','blocked','timed_out',
                'cancelled','succeeded','failed','delivery_unknown'
            )),
            ADD CONSTRAINT run_targets_attempt_nonnegative CHECK (attempt_no >= 0),
            ADD CONSTRAINT run_targets_error_code CHECK (error_code IS NULL OR error_code IN (
                'disabled','policy_denied','budget_denied','quota_denied','timeout',
                'cancelled','provider_error','delivery_unknown','invalid_response',
                'internal_error'
            )),
            ADD CONSTRAINT run_targets_state_error_shape CHECK (
                (state IN ('blocked','timed_out','cancelled','failed','delivery_unknown'))
                = (error_code IS NOT NULL)
            ),
            ADD CONSTRAINT run_targets_context_scope CHECK (
                context_snapshot_id IS NULL OR acquisition_mode='official_api'
            );

        CREATE FUNCTION protect_run_lifecycle() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.state IN ('completed','completed_partial','failed','cancelled') AND
               ROW(NEW.state,NEW.error_code,NEW.comparison_id,NEW.terminal_at)
               IS DISTINCT FROM
               ROW(OLD.state,OLD.error_code,OLD.comparison_id,OLD.terminal_at) THEN
                RAISE EXCEPTION 'Terminal run lifecycle is immutable';
            END IF;
            IF NEW.state<>OLD.state THEN
                IF NOT (
                    (OLD.state='queued' AND NEW.state IN ('running','cancelled','failed')) OR
                    (OLD.state='running' AND NEW.state IN (
                        'awaiting_manual','synthesizing','failed','cancelled'
                    )) OR
                    (OLD.state='awaiting_manual' AND NEW.state IN (
                        'synthesizing','failed','cancelled'
                    )) OR
                    (OLD.state='synthesizing' AND NEW.state IN (
                        'completed','completed_partial','failed','cancelled'
                    ))
                ) THEN
                    RAISE EXCEPTION 'Invalid run lifecycle transition % -> %', OLD.state, NEW.state;
                END IF;
                IF NEW.revision<>OLD.revision+1 THEN
                    RAISE EXCEPTION 'Run transition must increment revision exactly once';
                END IF;
            ELSIF NEW.revision<>OLD.revision THEN
                RAISE EXCEPTION 'Run revision changes only with lifecycle state';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER runs_lifecycle_guard
            BEFORE UPDATE ON runs
            FOR EACH ROW EXECUTE FUNCTION protect_run_lifecycle();

        CREATE FUNCTION protect_target_lifecycle() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            parent_state TEXT;
        BEGIN
            IF NEW.state<>OLD.state THEN
                SELECT state INTO parent_state FROM runs WHERE run_id=OLD.run_id;
                IF parent_state IN ('completed','completed_partial','failed','cancelled') THEN
                    RAISE EXCEPTION 'Terminal run rejects target transitions';
                END IF;
                IF NOT (
                    (OLD.state='pending' AND NEW.state IN (
                        'in_flight','blocked','timed_out','cancelled'
                    )) OR
                    (OLD.state='in_flight' AND NEW.state IN (
                        'succeeded','failed','delivery_unknown','timed_out','cancelled'
                    )) OR
                    (OLD.state='awaiting_manual' AND NEW.state IN (
                        'succeeded','timed_out','cancelled'
                    ))
                ) THEN
                    RAISE EXCEPTION 'Invalid target lifecycle transition % -> %', OLD.state, NEW.state;
                END IF;
            END IF;
            IF NEW.attempt_no<OLD.attempt_no OR NEW.attempt_no>OLD.attempt_no+1 THEN
                RAISE EXCEPTION 'Target attempt number is not monotonic';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER run_targets_lifecycle_guard
            BEFORE UPDATE ON run_targets
            FOR EACH ROW EXECUTE FUNCTION protect_target_lifecycle();

        ALTER TABLE run_targets
            ADD CONSTRAINT run_targets_run_target_unique UNIQUE (run_id, target_id);
        ALTER TABLE model_responses
            ADD CONSTRAINT model_responses_target_response_unique
            UNIQUE (target_id, response_id);

        CREATE TABLE run_events (
            event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID NOT NULL REFERENCES runs(run_id),
            sequence BIGINT NOT NULL CHECK (sequence > 0),
            trace_id UUID NOT NULL,
            schema_version SMALLINT NOT NULL DEFAULT 1 CHECK (schema_version=1),
            kind TEXT NOT NULL CHECK (kind IN (
                'run_state','target_state','original_saved','report_published'
            )),
            target_id UUID,
            previous_state TEXT,
            state TEXT,
            reason TEXT,
            response_id UUID,
            comparison_id UUID,
            version INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (run_id, sequence),
            FOREIGN KEY (run_id, target_id)
                REFERENCES run_targets(run_id, target_id),
            FOREIGN KEY (target_id, response_id)
                REFERENCES model_responses(target_id, response_id),
            CHECK (reason IS NULL OR reason IN (
                'disabled','policy_denied','budget_denied','quota_denied','timeout',
                'cancelled','provider_error','delivery_unknown','invalid_response',
                'internal_error'
            )),
            CHECK (
                (kind='run_state' AND target_id IS NULL AND state IS NOT NULL
                    AND state IN (
                        'queued','running','awaiting_manual','synthesizing',
                        'completed','completed_partial','failed','cancelled'
                    )
                    AND (previous_state IS NULL OR previous_state IN (
                        'queued','running','awaiting_manual','synthesizing',
                        'completed','completed_partial','failed','cancelled'
                    ))
                    AND response_id IS NULL AND comparison_id IS NULL AND version IS NULL)
                OR
                (kind='target_state' AND target_id IS NOT NULL
                    AND state IN (
                        'pending','in_flight','awaiting_manual','blocked','timed_out',
                        'cancelled','succeeded','failed','delivery_unknown'
                    )
                    AND (previous_state IS NULL OR previous_state IN (
                        'pending','in_flight','awaiting_manual','blocked','timed_out',
                        'cancelled','succeeded','failed','delivery_unknown'
                    ))
                    AND response_id IS NULL AND comparison_id IS NULL AND version IS NULL)
                OR
                (kind='original_saved' AND target_id IS NOT NULL AND response_id IS NOT NULL
                    AND state IS NULL AND previous_state IS NULL AND reason IS NULL
                    AND comparison_id IS NULL AND version IS NULL)
                OR
                (kind='report_published' AND comparison_id IS NOT NULL AND version>0
                    AND target_id IS NULL AND response_id IS NULL AND state IS NULL
                    AND previous_state IS NULL AND reason IS NULL)
            )
        );
        CREATE INDEX run_events_poll ON run_events(run_id, sequence);
        CREATE TRIGGER run_events_immutable
            BEFORE UPDATE OR DELETE ON run_events
            FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();
        CREATE TRIGGER run_events_no_truncate
            BEFORE TRUNCATE ON run_events
            FOR EACH STATEMENT EXECUTE FUNCTION reject_evidence_change();

        CREATE TABLE run_work (
            run_id UUID PRIMARY KEY REFERENCES runs(run_id),
            state TEXT NOT NULL CHECK (state IN ('available','leased','waiting','finished')),
            available_at TIMESTAMPTZ NOT NULL,
            lease_token UUID,
            lease_expires_at TIMESTAMPTZ,
            worker_id TEXT,
            fence BIGINT NOT NULL DEFAULT 0 CHECK (fence >= 0),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CHECK (
                (state='leased' AND lease_token IS NOT NULL
                    AND lease_expires_at IS NOT NULL AND worker_id IS NOT NULL)
                OR
                (state<>'leased' AND lease_token IS NULL
                    AND lease_expires_at IS NULL AND worker_id IS NULL)
            )
        );
        CREATE INDEX run_work_claim ON run_work(state, available_at);
        INSERT INTO run_work (run_id,state,available_at)
        SELECT run_id,
               CASE
                   WHEN state IN ('synthesizing','completed','completed_partial','failed','cancelled')
                       THEN 'finished'
                   WHEN state='awaiting_manual' THEN 'waiting'
                   ELSE 'available'
               END,
               CASE WHEN state='awaiting_manual' THEN deadline ELSE now() END
          FROM runs;

        CREATE TABLE provider_attempts (
            attempt_id UUID PRIMARY KEY,
            run_id UUID NOT NULL REFERENCES runs(run_id),
            target_id UUID NOT NULL,
            attempt_no INTEGER NOT NULL CHECK (attempt_no > 0),
            work_fence BIGINT NOT NULL CHECK (work_fence > 0),
            state TEXT NOT NULL CHECK (state IN (
                'prepared','dispatch_claimed','succeeded','failed',
                'delivery_unknown','timed_out','cancelled'
            )),
            request_hash TEXT NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
            grant_id UUID REFERENCES dispatch_grants(grant_id),
            response_id UUID,
            error_code TEXT,
            raw_receipt JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            dispatch_claimed_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            UNIQUE (target_id, attempt_no),
            FOREIGN KEY (run_id, target_id)
                REFERENCES run_targets(run_id, target_id),
            FOREIGN KEY (target_id, response_id)
                REFERENCES model_responses(target_id, response_id),
            CHECK (error_code IS NULL OR error_code IN (
                'disabled','policy_denied','budget_denied','quota_denied','timeout',
                'cancelled','provider_error','delivery_unknown','invalid_response',
                'internal_error'
            )),
            CHECK ((state='dispatch_claimed') = (dispatch_claimed_at IS NOT NULL AND finished_at IS NULL)),
            CHECK ((state IN ('succeeded','failed','delivery_unknown','timed_out','cancelled'))
                   = (finished_at IS NOT NULL)),
            CHECK (state<>'succeeded' OR response_id IS NOT NULL)
        );
        CREATE INDEX provider_attempts_target ON provider_attempts(target_id, attempt_no);

        CREATE FUNCTION protect_provider_attempt() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP='DELETE' THEN
                RAISE EXCEPTION 'Provider attempt evidence is immutable';
            END IF;
            IF ROW(
                NEW.attempt_id,NEW.run_id,NEW.target_id,NEW.attempt_no,
                NEW.work_fence,NEW.request_hash,NEW.grant_id,NEW.created_at
            ) IS DISTINCT FROM ROW(
                OLD.attempt_id,OLD.run_id,OLD.target_id,OLD.attempt_no,
                OLD.work_fence,OLD.request_hash,OLD.grant_id,OLD.created_at
            ) THEN
                RAISE EXCEPTION 'Provider attempt identity is immutable';
            END IF;
            IF NEW.state<>OLD.state AND NOT (
                (OLD.state='prepared' AND NEW.state IN (
                    'dispatch_claimed','failed','timed_out','cancelled'
                )) OR
                (OLD.state='dispatch_claimed' AND NEW.state IN (
                    'succeeded','failed','delivery_unknown','timed_out','cancelled'
                ))
            ) THEN
                RAISE EXCEPTION 'Invalid provider attempt transition % -> %', OLD.state, NEW.state;
            END IF;
            IF OLD.state IN ('succeeded','failed','delivery_unknown','timed_out','cancelled')
               AND NEW IS DISTINCT FROM OLD THEN
                RAISE EXCEPTION 'Terminal provider attempt is immutable';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER provider_attempts_guard
            BEFORE UPDATE OR DELETE ON provider_attempts
            FOR EACH ROW EXECUTE FUNCTION protect_provider_attempt();
        CREATE TRIGGER provider_attempts_no_truncate
            BEFORE TRUNCATE ON provider_attempts
            FOR EACH STATEMENT EXECUTE FUNCTION reject_evidence_change();
        """
    )


def downgrade():
    raise RuntimeError("Restore the verified pre-migration backup to roll back.")
