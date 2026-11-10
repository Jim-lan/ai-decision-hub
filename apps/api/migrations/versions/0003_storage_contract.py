"""Enforce owner and project scope across canonical prototype records."""

from alembic import op


revision = "0003_storage_contract"
down_revision = "0002_manual_runs"


def upgrade():
    op.execute("""
        ALTER TABLE projects
            ADD CONSTRAINT projects_owner_project_key UNIQUE (owner_id, project_id);
        ALTER TABLE conversations
            ADD CONSTRAINT conversations_project_conversation_key
            UNIQUE (project_id, conversation_id);
        ALTER TABLE messages
            ADD CONSTRAINT messages_conversation_message_key
            UNIQUE (conversation_id, message_id);

        ALTER TABLE runs ADD COLUMN project_id UUID;
        UPDATE runs r
           SET project_id = c.project_id
          FROM conversations c
         WHERE c.conversation_id = r.conversation_id;
        ALTER TABLE runs ALTER COLUMN project_id SET NOT NULL;

        ALTER TABLE runs
            ADD CONSTRAINT runs_owner_project_fkey
            FOREIGN KEY (owner_id, project_id)
            REFERENCES projects (owner_id, project_id) NOT VALID,
            ADD CONSTRAINT runs_project_conversation_fkey
            FOREIGN KEY (project_id, conversation_id)
            REFERENCES conversations (project_id, conversation_id) NOT VALID,
            ADD CONSTRAINT runs_conversation_message_fkey
            FOREIGN KEY (conversation_id, message_id)
            REFERENCES messages (conversation_id, message_id) NOT VALID;
        ALTER TABLE runs VALIDATE CONSTRAINT runs_owner_project_fkey;
        ALTER TABLE runs VALIDATE CONSTRAINT runs_project_conversation_fkey;
        ALTER TABLE runs VALIDATE CONSTRAINT runs_conversation_message_fkey;

        CREATE INDEX runs_project_created
            ON runs (project_id, created_at, run_id);

        ALTER TABLE messages
            ADD CONSTRAINT messages_source_hash_format
            CHECK (source_hash ~ '^[0-9a-f]{64}$');
        ALTER TABLE model_responses
            ADD CONSTRAINT model_responses_source_hash_format
            CHECK (source_hash ~ '^[0-9a-f]{64}$');

        CREATE TRIGGER audit_events_immutable
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();
    """)


def downgrade():
    raise RuntimeError("Restore the verified pre-migration backup to roll back.")
