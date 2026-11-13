"""Add durable login throttling and typed, scoped audit metadata."""

from alembic import op


revision = "0004_security_audit"
down_revision = "0003_storage_contract"


def upgrade():
    op.execute("""
        CREATE TABLE login_throttle (
            login TEXT PRIMARY KEY,
            failed_attempts INTEGER NOT NULL CHECK (failed_attempts > 0),
            window_started TIMESTAMPTZ NOT NULL,
            blocked_until TIMESTAMPTZ
        );

        ALTER TABLE audit_events DISABLE TRIGGER audit_events_immutable;
        ALTER TABLE audit_events
            ADD COLUMN schema_version SMALLINT,
            ADD COLUMN project_id UUID,
            ADD COLUMN outcome TEXT;

        UPDATE audit_events
           SET schema_version = CASE WHEN action IN (
                   'login', 'login_denied', 'logout', 'project_created',
                   'conversation_created', 'message_appended', 'run_created',
                   'run_transition', 'target_transition', 'context_allowed',
                   'context_denied', 'dispatch_attempt', 'manual_original_imported',
                   'budget_reserved', 'budget_denied', 'usage_reconciled',
                   'report_published', 'decision_saved', 'provider_config_changed',
                   'project_purged', 'project_exported', 'project_imported'
               ) THEN 1 ELSE 0 END,
               outcome = CASE
                   WHEN action IN ('login_denied', 'context_denied', 'budget_denied') THEN 'denied'
                   WHEN action IN (
                       'login', 'logout', 'project_created', 'conversation_created',
                       'message_appended', 'run_created', 'manual_original_imported'
                   ) THEN 'accepted'
                   ELSE 'unknown'
               END;

        UPDATE audit_events a
           SET project_id = p.project_id
          FROM projects p
         WHERE a.action = 'project_created' AND a.resource_id = p.project_id;
        UPDATE audit_events a
           SET project_id = c.project_id
          FROM conversations c
         WHERE a.action = 'conversation_created' AND a.resource_id = c.conversation_id;
        UPDATE audit_events a
           SET project_id = c.project_id
          FROM messages m JOIN conversations c USING (conversation_id)
         WHERE a.action = 'message_appended' AND a.resource_id = m.message_id;
        UPDATE audit_events a
           SET project_id = r.project_id
          FROM runs r
         WHERE a.action = 'run_created' AND a.resource_id = r.run_id;
        UPDATE audit_events a
           SET project_id = r.project_id
          FROM model_responses mr
          JOIN run_targets rt USING (target_id)
          JOIN runs r USING (run_id)
         WHERE a.action = 'manual_original_imported' AND a.resource_id = mr.response_id;

        ALTER TABLE audit_events
            ALTER COLUMN schema_version SET DEFAULT 1,
            ALTER COLUMN schema_version SET NOT NULL,
            ALTER COLUMN outcome SET NOT NULL,
            ADD CONSTRAINT audit_events_schema_version CHECK (schema_version IN (0, 1)),
            ADD CONSTRAINT audit_events_typed_action CHECK (
                schema_version = 0 OR action IN (
                    'login', 'login_denied', 'logout', 'project_created',
                    'conversation_created', 'message_appended', 'run_created',
                    'run_transition', 'target_transition', 'context_allowed',
                    'context_denied', 'dispatch_attempt', 'manual_original_imported',
                    'budget_reserved', 'budget_denied', 'usage_reconciled',
                    'report_published', 'decision_saved', 'provider_config_changed',
                    'project_purged', 'project_exported', 'project_imported'
                )
            ),
            ADD CONSTRAINT audit_events_typed_outcome CHECK (
                schema_version = 0 OR outcome IN (
                    'accepted', 'denied', 'failed', 'partial', 'cancelled', 'unknown'
                )
            );
        CREATE INDEX audit_events_owner_project_created
            ON audit_events (owner_id, project_id, created_at, event_id);
        ALTER TABLE audit_events ENABLE TRIGGER audit_events_immutable;

        CREATE FUNCTION require_typed_audit_insert() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.schema_version IS DISTINCT FROM 1 THEN
                RAISE EXCEPTION 'New audit records require the current typed schema';
            END IF;
            IF NEW.outcome IS NULL THEN
                NEW.outcome = CASE
                    WHEN NEW.action = 'login_denied' THEN 'denied'
                    WHEN NEW.action IN (
                        'login', 'logout', 'project_created', 'conversation_created',
                        'message_appended', 'run_created', 'manual_original_imported'
                    ) THEN 'accepted'
                    ELSE NULL
                END;
            END IF;
            IF NEW.outcome IS NULL THEN
                RAISE EXCEPTION 'New audit records require an explicit outcome';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER audit_events_typed_insert
            BEFORE INSERT ON audit_events
            FOR EACH ROW EXECUTE FUNCTION require_typed_audit_insert();
        CREATE TRIGGER audit_events_no_truncate
            BEFORE TRUNCATE ON audit_events
            FOR EACH STATEMENT EXECUTE FUNCTION reject_evidence_change();
    """)


def downgrade():
    raise RuntimeError("Restore the verified pre-migration backup to roll back.")
