from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from unittest.mock import Mock
from uuid import uuid4

import psycopg
import pytest

from app import workspace
from app.db import connect, read_secret
from app.ports import ConversationRepository


def test_workspace_helpers_consume_substitutable_repository(monkeypatch):
    substitute = Mock(spec=ConversationRepository)
    project_id = uuid4()
    conversation_id = uuid4()
    owner_id = uuid4()
    project = {"project_id": project_id}
    conversation = {"conversation_id": conversation_id, "project_id": project_id}
    message = {"conversation_id": conversation_id, "content": "exact"}
    substitute.get_project.return_value = project
    substitute.get_conversation.return_value = conversation
    substitute.append_message.return_value = message
    monkeypatch.setattr(workspace, "repository", lambda connection: substitute)

    assert workspace.require_project(object(), project_id, owner_id) == project
    assert workspace.conversation(object(), conversation_id, owner_id, lock=True) == conversation
    assert workspace.insert_message(object(), conversation_id, "exact") == message
    substitute.get_project.assert_called_once_with(project_id, owner_id)
    substitute.get_conversation.assert_called_once_with(conversation_id, owner_id, lock=True)
    substitute.append_message.assert_called_once_with(conversation_id, "exact")


def test_session_and_csrf(client):
    assert client.get("/v1/auth/session").status_code == 200
    res = client.post("/v1/projects", headers={"Origin":"https://untrusted.invalid"}, json={"name":"Denied"})
    assert res.status_code == 403 and res.json()["trace_id"] == res.headers["X-Trace-ID"]
    token = client.cookies.get("hub_session")
    assert client.post("/v1/auth/logout").status_code == 204
    client.cookies.set("hub_session", token)
    assert client.get("/v1/projects").status_code == 401
    assert client.post("/v1/auth/login", json={"password":"invalid"}).status_code == 401


def test_scoped_resources(client):
    with connect() as conn:
        owner = conn.execute("INSERT INTO users (login,password_hash) VALUES (%s,'unused') RETURNING user_id",
                             (str(uuid4()),)).fetchone()["user_id"]
        p = conn.execute("INSERT INTO projects (owner_id,name) VALUES (%s,'Other') RETURNING project_id",
                         (owner,)).fetchone()["project_id"]
        c = conn.execute("INSERT INTO conversations (project_id,title) VALUES (%s,'Hidden') RETURNING conversation_id",
                         (p,)).fetchone()["conversation_id"]
    assert client.get(f"/v1/projects/{p}").status_code == 404
    assert client.get(f"/v1/conversations/{c}/messages").status_code == 404
    assert client.post(f"/v1/conversations/{c}/messages", json={"content":"test"}).status_code == 404


def test_order_pagination_and_immutable_evidence(client, thread):
    path = f"/v1/conversations/{thread['conversation_id']}/messages"
    inputs = ["  Original text\n", "中文问题"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda content:client.post(path, json={"content":content}), inputs))
    assert all(r.status_code == 201 for r in responses)
    first = client.get(path, params={"limit":1}).json()
    second = client.get(path, params={"limit":1, "cursor":first["next_cursor"]}).json()
    records = first["items"] + second["items"]
    assert [r["sequence"] for r in records] == [1,2] and second["next_cursor"] is None
    assert {r["content"] for r in records} == set(inputs)
    assert all(r["source_hash"] == sha256(r["content"].encode()).hexdigest() for r in records)
    assert client.get(path, params={"cursor":"bad"}).status_code == 400
    with pytest.raises(psycopg.errors.RaiseException), connect() as conn:
        conn.execute("UPDATE messages SET content='changed' WHERE message_id=%s", (records[0]["message_id"],))


def test_project_history_is_literal_scoped_stable_and_reopenable(client, thread):
    project_id = thread["project_id"]
    other = client.post("/v1/projects", json={"name": "Other project"}).json()
    other_thread = client.post("/v1/conversations", json={
        "project_id": other["project_id"], "title": "Other thread",
    }).json()
    for conversation_id, content in (
        (thread["conversation_id"], "First %_ literal marker 中文"),
        (thread["conversation_id"], "Second %_ LITERAL marker"),
        (thread["conversation_id"], "Third %_ literal marker"),
        (other_thread["conversation_id"], "Foreign %_ literal marker"),
    ):
        assert client.post(f"/v1/conversations/{conversation_id}/messages",
                           json={"content": content}).status_code == 201

    path = f"/v1/projects/{project_id}/history"
    first = client.get(path, params={"q": "%_ literal", "limit": 1}).json()
    second = client.get(path, params={
        "q": "%_ literal", "limit": 1, "cursor": first["next_cursor"],
    }).json()
    third = client.get(path, params={
        "q": "%_ literal", "limit": 1, "cursor": second["next_cursor"],
    }).json()
    hits = first["items"] + second["items"] + third["items"]
    assert len(hits) == 3 and third["next_cursor"] is None
    assert all(hit["project_id"] == project_id and hit["kind"] == "message" for hit in hits)
    assert {hit["excerpt"] for hit in hits} == {
        "First %_ literal marker 中文", "Second %_ LITERAL marker",
        "Third %_ literal marker",
    }

    assert client.get(path, params={"q": "different", "cursor": first["next_cursor"]}).status_code == 400
    assert client.get(f"/v1/projects/{other['project_id']}/history", params={
        "q": "%_ literal", "cursor": first["next_cursor"],
    }).status_code == 400
    second_payload = second["next_cursor"].split(".")[0]
    first_signature = first["next_cursor"].split(".")[1]
    tampered = f"{second_payload}.{first_signature}"
    assert client.get(path, params={"q": "%_ literal", "cursor": tampered}).status_code == 400
    malformed = workspace.encode_cursor({
        "project": str(project_id), "query": sha256(b"%_ literal").hexdigest(),
        "created": 1, "kind": "message", "resource": False,
    })
    assert client.get(path, params={"q": "%_ literal", "cursor": malformed}).status_code == 400
    assert client.get(path, params={"q": " "}).status_code == 422

    assert client.post("/v1/auth/logout").status_code == 204
    assert client.post("/v1/auth/login", json={"password": read_secret("OWNER_PASSWORD")}).status_code == 204
    reopened = client.get(f"/v1/conversations/{thread['conversation_id']}/messages").json()["items"]
    assert {item["content"] for item in reopened} >= {
        "First %_ literal marker 中文", "Second %_ LITERAL marker",
        "Third %_ literal marker",
    }


def test_invalid_message_creates_no_business_or_success_audit(client, thread):
    path = f"/v1/conversations/{thread['conversation_id']}/messages"
    with connect() as conn:
        before_messages = conn.execute("SELECT count(*) AS count FROM messages").fetchone()["count"]
        before_audit = conn.execute("""SELECT count(*) AS count FROM audit_events
            WHERE action='message_appended'""").fetchone()["count"]
    assert client.post(path, json={"content": " "}).status_code == 422
    assert client.post(path, json={"content": "x" * 64001}).status_code == 422
    with connect() as conn:
        assert conn.execute("SELECT count(*) AS count FROM messages").fetchone()["count"] == before_messages
        assert conn.execute("""SELECT count(*) AS count FROM audit_events
            WHERE action='message_appended'""").fetchone()["count"] == before_audit
