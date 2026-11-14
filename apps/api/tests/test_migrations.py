from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import os
from uuid import uuid4

from alembic import command
from alembic.config import Config
import psycopg
from psycopg import sql
import pytest
from sqlalchemy.exc import IntegrityError

from app.db import connection_args, connect


@contextmanager
def isolated_database():
    name = "test_migration_" + uuid4().hex
    admin_args = connection_args() | {"dbname": "postgres"}
    previous = os.environ["PGDATABASE"]
    with psycopg.connect(**admin_args, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    os.environ["PGDATABASE"] = name
    try:
        yield
    finally:
        os.environ["PGDATABASE"] = previous
        with psycopg.connect(**admin_args, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def upgrade(revision):
    command.upgrade(Config("alembic.ini"), revision)


def seed_legacy(*, mismatched_message=False):
    identifiers = {name: uuid4() for name in (
        "owner", "project", "conversation", "message", "other_project",
        "other_conversation", "other_message", "run", "target", "response", "audit",
    )}
    content = "Exact legacy text\nwith Unicode: 测试"
    source_hash = hashlib.sha256(content.encode()).hexdigest()
    deadline = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    with connect() as conn:
        conn.execute("INSERT INTO users (user_id,login,password_hash) VALUES (%s,%s,'unused')",
                     (identifiers["owner"], str(identifiers["owner"])))
        conn.execute("INSERT INTO projects (project_id,owner_id,name) VALUES (%s,%s,'A')",
                     (identifiers["project"], identifiers["owner"]))
        conn.execute("INSERT INTO projects (project_id,owner_id,name) VALUES (%s,%s,'B')",
                     (identifiers["other_project"], identifiers["owner"]))
        conn.execute("INSERT INTO conversations (conversation_id,project_id,title) VALUES (%s,%s,'A1')",
                     (identifiers["conversation"], identifiers["project"]))
        conn.execute("INSERT INTO conversations (conversation_id,project_id,title) VALUES (%s,%s,'B1')",
                     (identifiers["other_conversation"], identifiers["other_project"]))
        conn.execute("""INSERT INTO messages
            (message_id,conversation_id,sequence,role,content,source_hash)
            VALUES (%s,%s,1,'user',%s,%s)""",
            (identifiers["message"], identifiers["conversation"], content, source_hash))
        conn.execute("""INSERT INTO messages
            (message_id,conversation_id,sequence,role,content,source_hash)
            VALUES (%s,%s,1,'user','other',%s)""",
            (identifiers["other_message"], identifiers["other_conversation"],
             hashlib.sha256(b"other").hexdigest()))
        question = identifiers["other_message"] if mismatched_message else identifiers["message"]
        conn.execute("""INSERT INTO runs
            (run_id,conversation_id,message_id,owner_id,request_key,request_hash,deadline)
            VALUES (%s,%s,%s,%s,'legacy-key','legacy-fingerprint',%s)""",
            (identifiers["run"], identifiers["conversation"], question, identifiers["owner"], deadline))
        conn.execute("""INSERT INTO run_targets
            (target_id,run_id,provider,alias,model_id,gateway,routing_mode)
            VALUES (%s,%s,'manual','user-declared','declared-model','manual','user_declared')""",
            (identifiers["target"], identifiers["run"]))
        conn.execute("""INSERT INTO model_responses
            (response_id,target_id,actual_model_id,model_family,identity_confidence,
             acquisition_mode,content,source_hash)
            VALUES (%s,%s,'declared-model','unknown','user_declared','manual',%s,%s)""",
            (identifiers["response"], identifiers["target"], content, source_hash))
        conn.execute("""INSERT INTO audit_events (event_id,owner_id,action,resource_id,trace_id)
            VALUES (%s,%s,'legacy_import',%s,%s)""",
            (identifiers["audit"], identifiers["owner"], identifiers["run"], uuid4()))
    return identifiers, content, source_hash, deadline


def test_empty_database_upgrades_to_head_idempotently():
    with isolated_database():
        upgrade("0003_storage_contract")
        upgrade("0003_storage_contract")
        with connect() as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "0003_storage_contract"
            project_id = conn.execute("""SELECT is_nullable FROM information_schema.columns
                WHERE table_name='runs' AND column_name='project_id'""").fetchone()
            assert project_id == {"is_nullable": "NO"}


def test_populated_legacy_database_upgrades_idempotently_and_preserves_evidence():
    with isolated_database():
        upgrade("0002_manual_runs")
        ids, content, source_hash, deadline = seed_legacy()
        upgrade("0003_storage_contract")
        upgrade("0003_storage_contract")
        with connect() as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "0003_storage_contract"
            run = conn.execute("SELECT project_id,message_id,deadline FROM runs WHERE run_id=%s",
                               (ids["run"],)).fetchone()
            assert run == {"project_id": ids["project"], "message_id": ids["message"], "deadline": deadline}
            original = conn.execute("SELECT content,source_hash FROM model_responses WHERE response_id=%s",
                                    (ids["response"],)).fetchone()
            assert original == {"content": content, "source_hash": source_hash}
            unused_message = uuid4()
            conn.execute("""INSERT INTO messages
                (message_id,conversation_id,sequence,role,content,source_hash)
                VALUES (%s,%s,2,'user','scope check',%s)""",
                (unused_message, ids["conversation"], hashlib.sha256(b"scope check").hexdigest()))
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                with conn.transaction():
                    conn.execute("""INSERT INTO runs
                        (project_id,conversation_id,message_id,owner_id,request_key,request_hash)
                        VALUES (%s,%s,%s,%s,'bad-scope','x')""",
                        (ids["other_project"], ids["conversation"], unused_message, ids["owner"]))
            with pytest.raises(psycopg.errors.CheckViolation):
                with conn.transaction():
                    conn.execute("""INSERT INTO messages
                        (conversation_id,sequence,role,content,source_hash)
                        VALUES (%s,3,'user','bad digest',%s)""",
                        (ids["conversation"], "g" * 64))
            for statement, value in (
                ("UPDATE messages SET content='changed' WHERE message_id=%s", ids["message"]),
                ("DELETE FROM model_responses WHERE response_id=%s", ids["response"]),
                ("UPDATE audit_events SET action='changed' WHERE event_id=%s", ids["audit"]),
            ):
                with pytest.raises(psycopg.errors.RaiseException):
                    with conn.transaction():
                        conn.execute(statement, (value,))


def test_invalid_legacy_scope_aborts_migration_without_partial_schema_change():
    with isolated_database():
        upgrade("0002_manual_runs")
        ids, content, source_hash, _ = seed_legacy(mismatched_message=True)
        with pytest.raises(IntegrityError) as error:
            upgrade("0003_storage_contract")
        assert isinstance(error.value.orig, psycopg.errors.ForeignKeyViolation)
        with connect() as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "0002_manual_runs"
            assert conn.execute("""SELECT count(*) AS count FROM information_schema.columns
                WHERE table_name='runs' AND column_name='project_id'""").fetchone()["count"] == 0
            original = conn.execute("SELECT content,source_hash FROM model_responses WHERE response_id=%s",
                                    (ids["response"],)).fetchone()
            assert original == {"content": content, "source_hash": source_hash}


def test_security_migration_types_known_audit_and_preserves_unknown_legacy_rows():
    with isolated_database():
        upgrade("0002_manual_runs")
        ids, _, _, _ = seed_legacy()
        upgrade("0003_storage_contract")
        known_event = uuid4()
        with connect() as conn:
            conn.execute("""INSERT INTO audit_events
                (event_id,owner_id,action,resource_id,trace_id)
                VALUES (%s,%s,'project_created',%s,%s)""",
                (known_event, ids["owner"], ids["project"], uuid4()))
        upgrade("head")
        upgrade("head")
        with connect() as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "0009_attempt_fencing"
            known = conn.execute("""SELECT schema_version,project_id,outcome FROM audit_events
                WHERE event_id=%s""", (known_event,)).fetchone()
            assert known == {"schema_version": 1, "project_id": ids["project"], "outcome": "accepted"}
            legacy = conn.execute("""SELECT schema_version,project_id,outcome FROM audit_events
                WHERE event_id=%s""", (ids["audit"],)).fetchone()
            assert legacy == {"schema_version": 0, "project_id": None, "outcome": "unknown"}
            request = conn.execute("""SELECT request_schema_version,normalized_request,
                max_cost_microusd FROM runs WHERE run_id=%s""", (ids["run"],)).fetchone()
            assert request == {
                "request_schema_version": 0,
                "normalized_request": None,
                "max_cost_microusd": None,
            }
            lifecycle = conn.execute("""SELECT run.state AS run_state,
                run.revision, target.state AS target_state, work.state AS work_state
                FROM runs run
                JOIN run_targets target ON target.run_id=run.run_id
                JOIN run_work work ON work.run_id=run.run_id
                WHERE run.run_id=%s""", (ids["run"],)).fetchone()
            assert lifecycle == {
                "run_state": "synthesizing", "revision": 1,
                "target_state": "succeeded", "work_state": "finished",
            }
            attempt_id = uuid4()
            conn.execute("""INSERT INTO provider_attempts (
                attempt_id,run_id,target_id,attempt_no,work_fence,state,request_hash,
                error_code,finished_at
            ) VALUES (%s,%s,%s,1,1,'failed',%s,'internal_error',clock_timestamp())""",
                (attempt_id, ids["run"], ids["target"], "a" * 64))
            with pytest.raises(psycopg.errors.RaiseException):
                with conn.transaction():
                    conn.execute("DELETE FROM provider_attempts WHERE attempt_id=%s", (attempt_id,))
            old_denied = uuid4()
            old_success = uuid4()
            conn.execute("""INSERT INTO audit_events
                (event_id,owner_id,action,resource_id,trace_id)
                VALUES (%s,%s,'login_denied',NULL,%s),
                       (%s,%s,'project_created',%s,%s)""",
                (old_denied, ids["owner"], uuid4(), old_success, ids["owner"],
                 ids["project"], uuid4()))
            compatibility = conn.execute("""SELECT event_id,schema_version,outcome
                FROM audit_events WHERE event_id IN (%s,%s)""",
                (old_denied, old_success)).fetchall()
            assert {row["event_id"]: (row["schema_version"], row["outcome"])
                    for row in compatibility} == {
                old_denied: (1, "denied"), old_success: (1, "accepted"),
            }
            with pytest.raises(psycopg.errors.CheckViolation):
                with conn.transaction():
                    conn.execute("""INSERT INTO audit_events
                        (owner_id,action,outcome,trace_id) VALUES (%s,'untyped','accepted',%s)""",
                        (ids["owner"], uuid4()))
            with pytest.raises(psycopg.errors.RaiseException):
                with conn.transaction():
                    conn.execute("""INSERT INTO audit_events
                        (schema_version,owner_id,action,outcome,trace_id)
                        VALUES (0,%s,'untyped','anything',%s)""",
                        (ids["owner"], uuid4()))
            count = conn.execute("SELECT count(*) AS count FROM audit_events").fetchone()["count"]
            with pytest.raises(psycopg.errors.RaiseException):
                with conn.transaction():
                    conn.execute("TRUNCATE audit_events")
            assert conn.execute("SELECT count(*) AS count FROM audit_events").fetchone()["count"] == count


def test_provider_identity_migration_preserves_unknown_history_and_freezes_snapshots():
    with isolated_database():
        upgrade("0002_manual_runs")
        ids, content, source_hash, _ = seed_legacy()
        upgrade("0004_security_audit")
        with connect() as conn:
            conn.execute("""UPDATE provider_models SET status='disabled'
                WHERE provider_id='manual' AND alias='user-declared'""")
            conn.execute("""INSERT INTO provider_models
                (provider_id,alias,gateway,routing_mode,status,last_verified_at)
                VALUES ('legacy-provider','legacy-alias','legacy-gateway','direct','enabled',now())""")
        upgrade("head")
        upgrade("head")
        with connect() as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "0009_attempt_fencing"
            manual = conn.execute("""SELECT acquisition_mode, app_name, configured_model_id,
                model_family, capabilities, pricing_status, privacy_profile, pricing_version,
                identity_confidence FROM provider_models
                WHERE provider_id='manual' AND alias='user-declared'""").fetchone()
            assert manual == {
                "acquisition_mode": "manual", "app_name": None,
                "configured_model_id": None, "model_family": None,
                "capabilities": ["text", "manual_import"], "pricing_status": "manual",
                "privacy_profile": "local_only", "pricing_version": None,
                "identity_confidence": "user_declared",
            }
            candidate = conn.execute("""SELECT status,last_verified_at,configured_model_id,
                model_family,pricing_status,privacy_profile,pricing_version,identity_confidence
                FROM provider_models WHERE provider_id='google'""").fetchone()
            assert candidate == {
                "status": "disabled", "last_verified_at": None,
                "configured_model_id": None, "model_family": None,
                "pricing_status": "unknown", "privacy_profile": "blocked",
                "pricing_version": None, "identity_confidence": "unknown",
            }
            legacy_catalog = conn.execute("""SELECT status,last_verified_at,acquisition_mode,
                app_name,configured_model_id,model_family,capabilities,pricing_status,
                privacy_profile,pricing_version,identity_confidence FROM provider_models
                WHERE provider_id='legacy-provider'""").fetchone()
            assert legacy_catalog.pop("last_verified_at") is not None
            assert legacy_catalog == {
                "status": "disabled",
                "acquisition_mode": "official_api", "app_name": None,
                "configured_model_id": None, "model_family": None,
                "capabilities": ["text"], "pricing_status": "unknown",
                "privacy_profile": "blocked", "pricing_version": None,
                "identity_confidence": "unknown",
            }
            for statement, value in (
                ("""UPDATE provider_models SET app_name=%s
                    WHERE provider_id='legacy-provider'""", " " * 160 + "x"),
                ("""UPDATE provider_models SET alias=%s
                    WHERE provider_id='legacy-provider'""", "\t"),
            ):
                with pytest.raises(psycopg.errors.CheckViolation):
                    with conn.transaction():
                        conn.execute(statement, (value,))
            target = conn.execute("""SELECT provider,alias,model_id,gateway,routing_mode,
                registry_status,acquisition_mode,model_family,identity_confidence,
                registry_verified_at FROM run_targets WHERE target_id=%s""",
                (ids["target"],)).fetchone()
            assert target == {
                "provider": "manual", "alias": "user-declared",
                "model_id": "declared-model", "gateway": "manual",
                "routing_mode": "user_declared", "registry_status": "unknown",
                "acquisition_mode": "manual", "model_family": None,
                "identity_confidence": "user_declared", "registry_verified_at": None,
            }
            original = conn.execute("""SELECT content,source_hash,actual_model_id,model_family,
                identity_confidence,resolved_provider_id,resolved_model_id,declared_app,
                declared_model_id,elapsed_ms,input_tokens,output_tokens,actual_cost_microusd,
                attempt_no,context_snapshot_id,inclusion FROM model_responses
                WHERE response_id=%s""", (ids["response"],)).fetchone()
            assert original == {
                "content": content, "source_hash": source_hash,
                "actual_model_id": "declared-model", "model_family": "unknown",
                "identity_confidence": "user_declared", "resolved_provider_id": None,
                "resolved_model_id": None, "declared_app": None, "declared_model_id": None,
                "elapsed_ms": None, "input_tokens": None, "output_tokens": None,
                "actual_cost_microusd": None, "attempt_no": 0,
                "context_snapshot_id": None, "inclusion": "included",
            }
            conn.execute("""UPDATE provider_models SET status='enabled'
                WHERE provider_id='manual' AND alias='user-declared'""")
            second_run = conn.execute("""INSERT INTO runs
                (project_id,conversation_id,message_id,owner_id,request_key,request_hash)
                VALUES (%s,%s,%s,%s,'legacy-writer-after-0005','legacy') RETURNING run_id""",
                (ids["other_project"], ids["other_conversation"], ids["other_message"],
                 ids["owner"])).fetchone()["run_id"]
            old_writer_target = conn.execute("""INSERT INTO run_targets
                (run_id,provider,alias,model_id,gateway,routing_mode)
                VALUES (%s,'manual','user-declared','legacy-writer','manual','user_declared')
                RETURNING target_id,registry_status,acquisition_mode,identity_confidence""",
                (second_run,)).fetchone()
            assert old_writer_target == {
                "target_id": old_writer_target["target_id"], "registry_status": "enabled",
                "acquisition_mode": "manual", "identity_confidence": "user_declared",
            }
            with pytest.raises(psycopg.errors.CheckViolation):
                with conn.transaction():
                    conn.execute("""UPDATE provider_models
                        SET capabilities=ARRAY['text','text']
                        WHERE provider_id='manual' AND alias='user-declared'""")
            with pytest.raises(psycopg.errors.CheckViolation):
                with conn.transaction():
                    conn.execute("""INSERT INTO model_responses (
                        target_id,actual_model_id,model_family,identity_confidence,
                        acquisition_mode,content,source_hash,resolved_provider_id,
                        resolved_model_id
                    ) VALUES (%s,'fixture-model','Fixture Family','provider_reported',
                        'official_api','invalid identity',%s,' ','fixture-model')""",
                        (old_writer_target["target_id"],
                         hashlib.sha256(b"invalid identity").hexdigest()))
            with pytest.raises(psycopg.errors.RaiseException):
                with conn.transaction():
                    conn.execute("UPDATE run_targets SET run_id=%s WHERE target_id=%s",
                                 (second_run, ids["target"]))
            conn.execute("""UPDATE provider_models SET status='disabled', app_name='changed'
                WHERE provider_id='manual' AND alias='user-declared'""")
            assert conn.execute("""SELECT registry_status,app_name FROM run_targets
                WHERE target_id=%s""", (ids["target"],)).fetchone() == {
                    "registry_status": "unknown", "app_name": None,
                }
            with pytest.raises(psycopg.errors.RaiseException):
                with conn.transaction():
                    conn.execute("UPDATE run_targets SET model_family='relabeled' WHERE target_id=%s",
                                 (ids["target"],))
            with pytest.raises(psycopg.errors.CheckViolation):
                with conn.transaction():
                    conn.execute("UPDATE provider_models SET status='enabled' WHERE provider_id='google'")
