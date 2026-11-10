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
        upgrade("head")
        upgrade("head")
        with connect() as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "0003_storage_contract"
            project_id = conn.execute("""SELECT is_nullable FROM information_schema.columns
                WHERE table_name='runs' AND column_name='project_id'""").fetchone()
            assert project_id == {"is_nullable": "NO"}


def test_populated_legacy_database_upgrades_idempotently_and_preserves_evidence():
    with isolated_database():
        upgrade("0002_manual_runs")
        ids, content, source_hash, deadline = seed_legacy()
        upgrade("head")
        upgrade("head")
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
            upgrade("head")
        assert isinstance(error.value.orig, psycopg.errors.ForeignKeyViolation)
        with connect() as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "0002_manual_runs"
            assert conn.execute("""SELECT count(*) AS count FROM information_schema.columns
                WHERE table_name='runs' AND column_name='project_id'""").fetchone()["count"] == 0
            original = conn.execute("SELECT content,source_hash FROM model_responses WHERE response_id=%s",
                                    (ids["response"],)).fetchone()
            assert original == {"content": content, "source_hash": source_hash}
