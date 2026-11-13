"""Adopt the frozen provider registry and immutable identity snapshots."""

from alembic import op


revision = "0005_provider_identity"
down_revision = "0004_security_audit"


def upgrade():
    op.execute("""
        ALTER TABLE provider_models
            ADD COLUMN acquisition_mode TEXT,
            ADD COLUMN app_name TEXT,
            ADD COLUMN configured_model_id TEXT,
            ADD COLUMN model_family TEXT,
            ADD COLUMN capabilities TEXT[],
            ADD COLUMN pricing_status TEXT,
            ADD COLUMN privacy_profile TEXT,
            ADD COLUMN pricing_version TEXT,
            ADD COLUMN identity_confidence TEXT;

        UPDATE provider_models
           SET acquisition_mode = 'manual',
               app_name = NULL,
               configured_model_id = NULL,
               model_family = NULL,
               capabilities = ARRAY['text', 'manual_import'],
               pricing_status = 'manual',
               privacy_profile = 'local_only',
               pricing_version = NULL,
               identity_confidence = 'user_declared'
         WHERE provider_id = 'manual' AND alias = 'user-declared';

        UPDATE provider_models
           SET status = 'disabled',
               acquisition_mode = 'official_api',
               app_name = NULL,
               configured_model_id = NULL,
               model_family = NULL,
               capabilities = ARRAY['text'],
               pricing_status = 'unknown',
               privacy_profile = 'blocked',
               pricing_version = NULL,
               identity_confidence = 'unknown'
         WHERE acquisition_mode IS NULL;

        CREATE FUNCTION provider_capabilities_are_unique(values_to_check TEXT[])
        RETURNS BOOLEAN LANGUAGE sql IMMUTABLE AS $$
            SELECT cardinality(values_to_check) = count(DISTINCT capability)
              FROM unnest(values_to_check) AS item(capability);
        $$;

        ALTER TABLE provider_models
            ALTER COLUMN acquisition_mode SET NOT NULL,
            ALTER COLUMN capabilities SET NOT NULL,
            ALTER COLUMN pricing_status SET NOT NULL,
            ALTER COLUMN privacy_profile SET NOT NULL,
            ALTER COLUMN identity_confidence SET NOT NULL,
            ADD CONSTRAINT provider_models_status
                CHECK (status IN ('enabled', 'disabled')),
            ADD CONSTRAINT provider_models_acquisition
                CHECK (acquisition_mode IN ('official_api', 'manual')),
            ADD CONSTRAINT provider_models_capabilities
                CHECK (
                    cardinality(capabilities) > 0
                    AND capabilities <@ ARRAY['text', 'manual_import']::TEXT[]
                    AND provider_capabilities_are_unique(capabilities)
                ),
            ADD CONSTRAINT provider_models_nonblank_identity
                CHECK (
                    char_length(provider_id) BETWEEN 1 AND 160
                    AND provider_id ~ '[^[:space:]]'
                    AND char_length(alias) BETWEEN 1 AND 160
                    AND alias ~ '[^[:space:]]'
                    AND char_length(gateway) BETWEEN 1 AND 160
                    AND gateway ~ '[^[:space:]]'
                    AND char_length(routing_mode) BETWEEN 1 AND 160
                    AND routing_mode ~ '[^[:space:]]'
                    AND (app_name IS NULL OR (
                        char_length(app_name) BETWEEN 1 AND 160
                        AND app_name ~ '[^[:space:]]'
                    ))
                    AND (configured_model_id IS NULL OR (
                        char_length(configured_model_id) BETWEEN 1 AND 160
                        AND configured_model_id ~ '[^[:space:]]'
                    ))
                    AND (model_family IS NULL OR (
                        char_length(model_family) BETWEEN 1 AND 160
                        AND model_family ~ '[^[:space:]]'
                    ))
                    AND (pricing_version IS NULL OR (
                        char_length(pricing_version) BETWEEN 1 AND 160
                        AND pricing_version ~ '[^[:space:]]'
                    ))
                ),
            ADD CONSTRAINT provider_models_pricing
                CHECK (pricing_status IN ('verified_free', 'verified_priced', 'unknown', 'manual')),
            ADD CONSTRAINT provider_models_privacy
                CHECK (privacy_profile IN ('local_only', 'allowlisted', 'blocked')),
            ADD CONSTRAINT provider_models_confidence
                CHECK (identity_confidence IN ('provider_reported', 'user_declared', 'unknown')),
            ADD CONSTRAINT provider_models_enabled_official_is_verified
                CHECK (
                    status = 'disabled'
                    OR acquisition_mode = 'manual'
                    OR (
                        last_verified_at IS NOT NULL
                        AND configured_model_id IS NOT NULL
                        AND model_family IS NOT NULL
                        AND pricing_status IN ('verified_free', 'verified_priced')
                        AND pricing_version IS NOT NULL
                        AND privacy_profile = 'allowlisted'
                        AND identity_confidence = 'provider_reported'
                    )
                ),
            ADD CONSTRAINT provider_models_manual_is_local
                CHECK (
                    acquisition_mode <> 'manual'
                    OR (
                        gateway = 'manual'
                        AND pricing_status = 'manual'
                        AND privacy_profile = 'local_only'
                        AND identity_confidence = 'user_declared'
                        AND last_verified_at IS NULL
                    )
                );

        INSERT INTO provider_models (
            provider_id, alias, gateway, routing_mode, status, last_verified_at,
            acquisition_mode, app_name, configured_model_id, model_family,
            capabilities, pricing_status, privacy_profile, pricing_version,
            identity_confidence
        ) VALUES (
            'google', 'gemini-api-candidate', 'google-generative-language', 'direct',
            'disabled', NULL, 'official_api', 'Gemini API', NULL, NULL,
            ARRAY['text'], 'unknown', 'blocked', NULL, 'unknown'
        ) ON CONFLICT (provider_id, alias) DO NOTHING;

        ALTER TABLE run_targets
            ADD COLUMN registry_status TEXT,
            ADD COLUMN acquisition_mode TEXT,
            ADD COLUMN app_name TEXT,
            ADD COLUMN configured_model_id TEXT,
            ADD COLUMN model_family TEXT,
            ADD COLUMN capabilities TEXT[],
            ADD COLUMN pricing_status TEXT,
            ADD COLUMN privacy_profile TEXT,
            ADD COLUMN pricing_version TEXT,
            ADD COLUMN identity_confidence TEXT,
            ADD COLUMN registry_verified_at TIMESTAMPTZ;

        CREATE FUNCTION snapshot_target_identity_on_insert() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            catalog provider_models%ROWTYPE;
        BEGIN
            SELECT * INTO catalog FROM provider_models
             WHERE provider_id = NEW.provider AND alias = NEW.alias;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Provider registry selection is unavailable';
            END IF;
            IF catalog.status <> 'enabled' THEN
                RAISE EXCEPTION 'Provider registry selection is disabled';
            END IF;
            NEW.gateway := catalog.gateway;
            NEW.routing_mode := catalog.routing_mode;
            NEW.registry_status := catalog.status;
            NEW.acquisition_mode := catalog.acquisition_mode;
            NEW.app_name := catalog.app_name;
            NEW.configured_model_id := catalog.configured_model_id;
            NEW.model_family := catalog.model_family;
            NEW.capabilities := catalog.capabilities;
            NEW.pricing_status := catalog.pricing_status;
            NEW.privacy_profile := catalog.privacy_profile;
            NEW.pricing_version := catalog.pricing_version;
            NEW.identity_confidence := catalog.identity_confidence;
            NEW.registry_verified_at := catalog.last_verified_at;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER run_targets_snapshot_insert
            BEFORE INSERT ON run_targets
            FOR EACH ROW EXECUTE FUNCTION snapshot_target_identity_on_insert();

        -- Legacy targets prove only their stored route and requested model. Do not
        -- relabel them with catalog metadata as it happens to exist at upgrade time.
        UPDATE run_targets
           SET registry_status = 'unknown',
               acquisition_mode = CASE
                   WHEN provider = 'manual' AND gateway = 'manual'
                       AND routing_mode = 'user_declared' THEN 'manual'
                   ELSE 'official_api'
               END,
               app_name = NULL,
               configured_model_id = NULL,
               model_family = NULL,
               capabilities = CASE
                   WHEN provider = 'manual' AND gateway = 'manual'
                       AND routing_mode = 'user_declared'
                       THEN ARRAY['text', 'manual_import']::TEXT[]
                   ELSE ARRAY['text']::TEXT[]
               END,
               pricing_status = CASE
                   WHEN provider = 'manual' AND gateway = 'manual'
                       AND routing_mode = 'user_declared' THEN 'manual'
                   ELSE 'unknown'
               END,
               privacy_profile = CASE
                   WHEN provider = 'manual' AND gateway = 'manual'
                       AND routing_mode = 'user_declared' THEN 'local_only'
                   ELSE 'blocked'
               END,
               pricing_version = NULL,
               identity_confidence = CASE
                   WHEN provider = 'manual' AND gateway = 'manual'
                       AND routing_mode = 'user_declared' THEN 'user_declared'
                   ELSE 'unknown'
               END,
               registry_verified_at = NULL;

        ALTER TABLE run_targets
            ALTER COLUMN registry_status SET NOT NULL,
            ALTER COLUMN acquisition_mode SET NOT NULL,
            ALTER COLUMN capabilities SET NOT NULL,
            ALTER COLUMN pricing_status SET NOT NULL,
            ALTER COLUMN privacy_profile SET NOT NULL,
            ALTER COLUMN identity_confidence SET NOT NULL,
            ADD CONSTRAINT run_targets_registry_status
                CHECK (registry_status IN ('enabled', 'disabled', 'unknown')),
            ADD CONSTRAINT run_targets_acquisition
                CHECK (acquisition_mode IN ('official_api', 'manual')),
            ADD CONSTRAINT run_targets_pricing
                CHECK (pricing_status IN ('verified_free', 'verified_priced', 'unknown', 'manual')),
            ADD CONSTRAINT run_targets_privacy
                CHECK (privacy_profile IN ('local_only', 'allowlisted', 'blocked')),
            ADD CONSTRAINT run_targets_confidence
                CHECK (identity_confidence IN ('provider_reported', 'user_declared', 'unknown')),
            ADD CONSTRAINT run_targets_capabilities
                CHECK (
                    cardinality(capabilities) > 0
                    AND capabilities <@ ARRAY['text', 'manual_import']::TEXT[]
                    AND provider_capabilities_are_unique(capabilities)
                ),
            ADD CONSTRAINT run_targets_nonblank_identity
                CHECK (
                    char_length(provider) BETWEEN 1 AND 160
                    AND provider ~ '[^[:space:]]'
                    AND char_length(alias) BETWEEN 1 AND 160
                    AND alias ~ '[^[:space:]]'
                    AND char_length(model_id) BETWEEN 1 AND 160
                    AND model_id ~ '[^[:space:]]'
                    AND char_length(gateway) BETWEEN 1 AND 160
                    AND gateway ~ '[^[:space:]]'
                    AND char_length(routing_mode) BETWEEN 1 AND 160
                    AND routing_mode ~ '[^[:space:]]'
                    AND (app_name IS NULL OR (
                        char_length(app_name) BETWEEN 1 AND 160
                        AND app_name ~ '[^[:space:]]'
                    ))
                    AND (configured_model_id IS NULL OR (
                        char_length(configured_model_id) BETWEEN 1 AND 160
                        AND configured_model_id ~ '[^[:space:]]'
                    ))
                    AND (model_family IS NULL OR (
                        char_length(model_family) BETWEEN 1 AND 160
                        AND model_family ~ '[^[:space:]]'
                    ))
                    AND (pricing_version IS NULL OR (
                        char_length(pricing_version) BETWEEN 1 AND 160
                        AND pricing_version ~ '[^[:space:]]'
                    ))
                );

        CREATE FUNCTION protect_target_identity_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' OR ROW(
                OLD.target_id, OLD.run_id, OLD.provider, OLD.alias, OLD.model_id,
                OLD.gateway, OLD.routing_mode,
                OLD.registry_status, OLD.acquisition_mode, OLD.app_name,
                OLD.configured_model_id, OLD.model_family, OLD.capabilities,
                OLD.pricing_status, OLD.privacy_profile, OLD.pricing_version,
                OLD.identity_confidence, OLD.registry_verified_at
            ) IS DISTINCT FROM ROW(
                NEW.target_id, NEW.run_id, NEW.provider, NEW.alias, NEW.model_id,
                NEW.gateway, NEW.routing_mode,
                NEW.registry_status, NEW.acquisition_mode, NEW.app_name,
                NEW.configured_model_id, NEW.model_family, NEW.capabilities,
                NEW.pricing_status, NEW.privacy_profile, NEW.pricing_version,
                NEW.identity_confidence, NEW.registry_verified_at
            ) THEN
                RAISE EXCEPTION 'Run target identity snapshots are immutable';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER run_targets_identity_immutable
            BEFORE UPDATE OR DELETE ON run_targets
            FOR EACH ROW EXECUTE FUNCTION protect_target_identity_snapshot();

        ALTER TABLE model_responses
            ADD COLUMN resolved_provider_id TEXT,
            ADD COLUMN resolved_model_id TEXT,
            ADD COLUMN model_version TEXT,
            ADD COLUMN declared_app TEXT,
            ADD COLUMN declared_model_id TEXT,
            ADD COLUMN elapsed_ms BIGINT,
            ADD COLUMN input_tokens BIGINT,
            ADD COLUMN output_tokens BIGINT,
            ADD COLUMN actual_cost_microusd BIGINT,
            ADD COLUMN attempt_no INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN context_snapshot_id UUID,
            ADD COLUMN inclusion TEXT NOT NULL DEFAULT 'included';

        ALTER TABLE model_responses
            ADD CONSTRAINT model_responses_confidence
                CHECK (identity_confidence IN ('provider_reported', 'user_declared', 'unknown')),
            ADD CONSTRAINT model_responses_acquisition
                CHECK (acquisition_mode IN ('official_api', 'manual')),
            ADD CONSTRAINT model_responses_resolved_pair
                CHECK ((resolved_provider_id IS NULL) = (resolved_model_id IS NULL)),
            ADD CONSTRAINT model_responses_nonblank_identity
                CHECK (
                    char_length(actual_model_id) BETWEEN 1 AND 160
                    AND actual_model_id ~ '[^[:space:]]'
                    AND char_length(model_family) BETWEEN 1 AND 160
                    AND model_family ~ '[^[:space:]]'
                    AND (resolved_provider_id IS NULL OR (
                        char_length(resolved_provider_id) BETWEEN 1 AND 160
                        AND resolved_provider_id ~ '[^[:space:]]'
                        AND lower(btrim(resolved_provider_id)) NOT IN
                            ('unknown', 'multi-model', 'unresolved')
                    ))
                    AND (resolved_model_id IS NULL OR (
                        char_length(resolved_model_id) BETWEEN 1 AND 160
                        AND resolved_model_id ~ '[^[:space:]]'
                        AND lower(btrim(resolved_model_id)) NOT IN
                            ('unknown', 'multi-model', 'unresolved')
                    ))
                    AND (model_version IS NULL OR (
                        char_length(model_version) BETWEEN 1 AND 160
                        AND model_version ~ '[^[:space:]]'
                    ))
                    AND (declared_app IS NULL OR (
                        char_length(declared_app) BETWEEN 1 AND 160
                        AND declared_app ~ '[^[:space:]]'
                    ))
                    AND (declared_model_id IS NULL OR (
                        char_length(declared_model_id) BETWEEN 1 AND 160
                        AND declared_model_id ~ '[^[:space:]]'
                    ))
                ),
            ADD CONSTRAINT model_responses_provider_reported_identity
                CHECK (
                    identity_confidence <> 'provider_reported'
                    OR resolved_provider_id IS NOT NULL
                ),
            ADD CONSTRAINT model_responses_manual_identity
                CHECK (
                    acquisition_mode <> 'manual'
                    OR (
                        resolved_provider_id IS NULL
                        AND resolved_model_id IS NULL
                        AND identity_confidence IN ('user_declared', 'unknown')
                    )
                ),
            ADD CONSTRAINT model_responses_nonnegative_measurements
                CHECK (
                    elapsed_ms >= 0
                    AND input_tokens >= 0
                    AND output_tokens >= 0
                    AND actual_cost_microusd >= 0
                    AND attempt_no >= 0
                ),
            ADD CONSTRAINT model_responses_inclusion
                CHECK (inclusion IN ('included', 'late_excluded'));
    """)


def downgrade():
    raise RuntimeError("Restore the verified pre-migration backup to roll back.")
