from contextlib import contextmanager
import logging
import socket
from threading import Event, Thread
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import httpx
import psycopg
import pytest
import uvicorn

from app.db import connect, read_secret
from app.main import app
from app import security, workspace


def reset_throttle():
    with connect() as conn:
        conn.execute("DELETE FROM login_throttle WHERE login='owner'")


@contextmanager
def live_server():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(
        app, log_config=None, access_log=False, lifespan="off",
    ))
    thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        Event().wait(0.01)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("Test server did not start")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        assert not thread.is_alive()


def test_session_expiry_revocation_and_cookie_policy(client, monkeypatch):
    token = client.cookies.get(security.cookie)
    with connect() as conn:
        stored = conn.execute("SELECT token_hash FROM sessions WHERE token_hash=%s",
                              (security.digest(token),)).fetchone()
        assert stored and token not in stored["token_hash"]
        conn.execute("UPDATE sessions SET expires_at=now()-interval '1 second' WHERE token_hash=%s",
                     (stored["token_hash"],))
    assert client.get("/v1/auth/session").status_code == 401
    with connect() as conn:
        assert not conn.execute("SELECT 1 FROM sessions WHERE token_hash=%s",
                                (stored["token_hash"],)).fetchone()

    login = client.post("/v1/auth/login", json={"password": read_secret("OWNER_PASSWORD")})
    assert login.status_code == 204
    cookie_header = login.headers["set-cookie"].lower()
    assert "httponly" in cookie_header and "samesite=strict" in cookie_header
    assert "secure" not in cookie_header
    replay = client.cookies.get(security.cookie)
    assert client.post("/v1/auth/logout").status_code == 204
    client.cookies.set(security.cookie, replay)
    assert client.get("/v1/auth/session").status_code == 401

    monkeypatch.setenv("PUBLIC_BASE_URL", "https://hub.test")
    with TestClient(app, headers={"Origin": "https://hub.test"}) as https_client:
        secure_login = https_client.post("/v1/auth/login",
                                         json={"password": read_secret("OWNER_PASSWORD")})
        assert secure_login.status_code == 204
        assert "secure" in secure_login.headers["set-cookie"].lower()


def test_origin_and_login_throttle_are_fail_closed_and_redacted(client):
    reset_throttle()
    marker = "PASSWORD-CANARY-DO-NOT-ECHO"
    missing = client.post("/v1/projects", headers={"Origin": ""}, json={"name": "Denied"})
    mismatch = client.post("/v1/projects", headers={"Origin": "https://untrusted.invalid"},
                           json={"name": "Denied"})
    assert missing.status_code == mismatch.status_code == 403
    assert marker not in missing.text + mismatch.text

    with TestClient(app, headers={"Origin": client.headers["Origin"]}) as anonymous:
        for _ in range(security.failed_attempt_limit - 1):
            denied = anonymous.post("/v1/auth/login", json={"password": marker})
            assert denied.status_code == 401 and marker not in denied.text
        limited = anonymous.post("/v1/auth/login", json={"password": marker})
        assert limited.status_code == 429 and marker not in limited.text
        still_limited = anonymous.post("/v1/auth/login",
                                       json={"password": read_secret("OWNER_PASSWORD")})
        assert still_limited.status_code == 429
    with connect() as conn:
        rows = conn.execute("""SELECT action,outcome FROM audit_events
            WHERE action='login_denied' ORDER BY created_at DESC LIMIT %s""",
            (security.failed_attempt_limit + 1,)).fetchall()
        assert len(rows) == security.failed_attempt_limit + 1
        assert all(row == {"action": "login_denied", "outcome": "denied"} for row in rows)
        assert not conn.execute("SELECT 1 FROM audit_events WHERE action LIKE %s", (f"%{marker}%",)).fetchone()
        conn.execute("UPDATE login_throttle SET blocked_until=now()-interval '1 second' WHERE login='owner'")
    with TestClient(app, headers={"Origin": client.headers["Origin"]}) as recovered:
        assert recovered.post("/v1/auth/login",
                              json={"password": read_secret("OWNER_PASSWORD")}).status_code == 204


def test_foreign_and_mixed_nested_resources_are_invisible(client, thread):
    marker = "FOREIGN-PRIVATE-MARKER"
    with connect() as conn:
        foreign_owner = conn.execute("""INSERT INTO users (login,password_hash)
            VALUES (%s,'unused') RETURNING user_id""", (str(uuid4()),)).fetchone()["user_id"]
        project = conn.execute("""INSERT INTO projects (owner_id,name)
            VALUES (%s,%s) RETURNING project_id""", (foreign_owner, marker)).fetchone()["project_id"]
        conversation = conn.execute("""INSERT INTO conversations (project_id,title)
            VALUES (%s,'Hidden') RETURNING conversation_id""", (project,)).fetchone()["conversation_id"]
        message = conn.execute("""INSERT INTO messages
            (conversation_id,sequence,role,content,source_hash)
            VALUES (%s,1,'user','foreign',%s) RETURNING message_id""",
            (conversation, security.digest("foreign"))).fetchone()["message_id"]
        run = conn.execute("""INSERT INTO runs
            (project_id,conversation_id,message_id,owner_id,request_key,request_hash)
            VALUES (%s,%s,%s,%s,%s,'foreign') RETURNING run_id""",
            (project, conversation, message, foreign_owner, str(uuid4()))).fetchone()["run_id"]
        target = conn.execute("""INSERT INTO run_targets
            (run_id,provider,alias,model_id,gateway,routing_mode)
            VALUES (%s,'manual','user-declared','foreign-model','manual','user_declared')
            RETURNING target_id""", (run,)).fetchone()["target_id"]

    for path in (f"/v1/projects/{project}", f"/v1/conversations/{conversation}",
                 f"/v1/conversations/{conversation}/messages", f"/v1/runs/{run}",
                 f"/v1/runs/{run}/responses"):
        response = client.get(path)
        assert response.status_code == 404 and marker not in response.text
    hidden_write = client.post(f"/v1/runs/{run}/manual-responses",
                               json={"target_id": str(target), "content": "probe"})
    assert hidden_write.status_code == 404 and marker not in hidden_write.text

    own_run = client.post("/v1/runs", headers={"Idempotency-Key": str(uuid4())}, json={
        "conversation_id": thread["conversation_id"], "question": "Own question",
        "model_targets": [{"provider": "manual", "model_id": "own-model"}],
    }).json()
    mixed = client.post(f"/v1/runs/{own_run['run_id']}/manual-responses",
                        json={"target_id": str(target), "content": "probe"})
    assert mixed.status_code == 404 and marker not in mixed.text


def test_audit_is_typed_scoped_redacted_and_atomic(client, monkeypatch, caplog):
    project_name = "Atomic project " + str(uuid4())
    project = client.post("/v1/projects", json={"name": "Scoped audit"}).json()
    conversation = client.post("/v1/conversations", json={
        "project_id": project["project_id"], "title": "Audit thread",
    }).json()
    message = client.post(f"/v1/conversations/{conversation['conversation_id']}/messages",
                          json={"content": "PRIVATE-PROMPT-CANARY"}).json()
    with connect() as conn:
        for action, resource in (
            ("project_created", project["project_id"]),
            ("conversation_created", conversation["conversation_id"]),
            ("message_appended", message["message_id"]),
        ):
            row = conn.execute("""SELECT schema_version,project_id,outcome FROM audit_events
                WHERE action=%s AND resource_id=%s""", (action, resource)).fetchone()
            assert row == {"schema_version": 1, "project_id": UUID(project["project_id"]),
                           "outcome": "accepted"}
        assert not conn.execute("SELECT 1 FROM audit_events WHERE action LIKE '%CANARY%'").fetchone()

    original_audit = security.audit

    def fail_after_audit(conn, action, trace, owner=None, resource=None, **kwargs):
        original_audit(conn, action, trace, owner, resource, **kwargs)
        raise RuntimeError("PRIVATE-EXCEPTION-CANARY")

    monkeypatch.setattr(workspace, "audit", fail_after_audit)
    token = client.cookies.get(security.cookie)
    with caplog.at_level(logging.ERROR, logger="ai_decision_hub.requests"):
        with live_server() as base_url, httpx.Client(
            base_url=base_url, headers={"Origin": client.headers["Origin"]},
            cookies={security.cookie: token},
        ) as isolated:
            failed = isolated.post("/v1/projects", json={"name": project_name})
    assert failed.status_code == 500
    assert failed.headers["content-type"].startswith("application/problem+json")
    assert failed.headers["cache-control"] == "no-store"
    assert failed.headers["x-trace-id"] == failed.json()["trace_id"]
    assert "PRIVATE-EXCEPTION-CANARY" not in failed.text
    assert "PRIVATE-EXCEPTION-CANARY" not in caplog.text
    assert failed.json()["trace_id"] in caplog.text
    with connect() as conn:
        assert not conn.execute("SELECT 1 FROM projects WHERE name=%s", (project_name,)).fetchone()
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.transaction():
                conn.execute("""UPDATE audit_events SET outcome='failed'
                    WHERE event_id=(SELECT event_id FROM audit_events LIMIT 1)""")
