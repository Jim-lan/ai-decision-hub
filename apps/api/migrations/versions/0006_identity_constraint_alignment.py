"""Align persisted identity string constraints with the frozen public contract."""

from alembic import op


revision = "0006_identity_constraints"
down_revision = "0005_provider_identity"


def upgrade():
    op.execute("""
        ALTER TABLE provider_models
            DROP CONSTRAINT provider_models_nonblank_identity,
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
                );

        ALTER TABLE run_targets
            DROP CONSTRAINT run_targets_nonblank_identity,
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

        ALTER TABLE model_responses
            DROP CONSTRAINT model_responses_nonblank_identity,
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
                );
    """)


def downgrade():
    raise RuntimeError("Restore the verified pre-migration backup to roll back.")
