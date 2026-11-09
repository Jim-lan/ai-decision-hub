from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from uuid import uuid4

import psycopg
import pytest

from app.db import connect


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
