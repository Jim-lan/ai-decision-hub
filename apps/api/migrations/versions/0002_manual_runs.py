"""Manual comparison runs and immutable originals."""
from alembic import op

revision = "0002_manual_runs"
down_revision = "0001_workspace"


def upgrade():
    op.execute("""
        CREATE TABLE provider_models (
            provider_id TEXT NOT NULL,
            alias TEXT NOT NULL,
            gateway TEXT NOT NULL,
            routing_mode TEXT NOT NULL,
            status TEXT NOT NULL,
            last_verified_at TIMESTAMPTZ,
            PRIMARY KEY (provider_id, alias)
        );
        INSERT INTO provider_models VALUES ('manual','user-declared','manual','user_declared','enabled',NULL);
        CREATE TABLE runs (
            run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations,
            message_id UUID NOT NULL UNIQUE REFERENCES messages,
            owner_id UUID NOT NULL REFERENCES users,
            request_key TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deadline TIMESTAMPTZ NOT NULL DEFAULT now() + interval '24 hours',
            UNIQUE (owner_id, request_key)
        );
        CREATE INDEX runs_conversation ON runs(conversation_id, created_at);
        CREATE TABLE run_targets (
            target_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID NOT NULL REFERENCES runs,
            provider TEXT NOT NULL,
            alias TEXT NOT NULL,
            model_id TEXT NOT NULL,
            gateway TEXT NOT NULL,
            routing_mode TEXT NOT NULL,
            UNIQUE (run_id, provider, model_id),
            FOREIGN KEY (provider, alias) REFERENCES provider_models
        );
        CREATE TABLE model_responses (
            response_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            target_id UUID UNIQUE NOT NULL REFERENCES run_targets,
            actual_model_id TEXT NOT NULL,
            model_family TEXT NOT NULL,
            identity_confidence TEXT NOT NULL,
            acquisition_mode TEXT NOT NULL,
            content TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TRIGGER responses_immutable BEFORE UPDATE OR DELETE ON model_responses
            FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();
    """)


def downgrade():
    raise RuntimeError("Restore the verified pre-migration backup to roll back.")
