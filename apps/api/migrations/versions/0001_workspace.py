"""Durable owner workspace and immutable conversation evidence."""
from alembic import op

revision = "0001_workspace"
down_revision = None


def upgrade():
    op.execute("""
        CREATE TABLE users (
            user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            login TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE sessions (
            token_hash TEXT PRIMARY KEY,
            owner_id UUID NOT NULL REFERENCES users,
            expires_at TIMESTAMPTZ NOT NULL
        );
        CREATE TABLE projects (
            project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_id UUID NOT NULL REFERENCES users,
            name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX projects_owner ON projects(owner_id, created_at, project_id);
        CREATE TABLE conversations (
            conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects,
            title TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX conversations_project ON conversations(project_id, created_at, conversation_id);
        CREATE TABLE messages (
            message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations,
            sequence BIGINT NOT NULL CHECK (sequence > 0),
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (conversation_id, sequence)
        );
        CREATE FUNCTION reject_evidence_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Evidence records are append-only';
        END; $$;
        CREATE TRIGGER messages_immutable BEFORE UPDATE OR DELETE ON messages
            FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();
        CREATE TABLE audit_events (
            event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_id UUID REFERENCES users,
            action TEXT NOT NULL,
            resource_id UUID,
            trace_id UUID NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)


def downgrade():
    raise RuntimeError("Restore the verified pre-migration backup to roll back.")
