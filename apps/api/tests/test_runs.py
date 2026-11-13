from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from app.db import connect
from app.runs import LegacyStart, Target
from app.security import digest


def start(client, thread):
    data = {"conversation_id":thread["conversation_id"], "question":"What are the options?",
            "model_targets":[{"provider":"manual", "model_id":name} for name in ("Model A","Model B")]}
    key = str(uuid4())
    headers = {"Idempotency-Key":key}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _:client.post("/v1/runs", json=data, headers=headers), range(2)))
    assert all(r.status_code == 202 for r in results)
    assert results[0].json()["run_id"] == results[1].json()["run_id"]
    assert client.post("/v1/runs", json=data | {"question":"Changed"}, headers=headers).status_code == 409
    assert len(client.get(f"/v1/conversations/{thread['conversation_id']}/messages").json()["items"]) == 1
    return results[0].json()


def test_two_originals_retry_and_conflict(client, thread):
    run = start(client, thread)
    path = f"/v1/runs/{run['run_id']}"
    assert run["status"] == "awaiting_manual"
    providers = {item["provider_id"]: item for item in client.get("/v1/providers").json()}
    assert providers["manual"] == {
        "provider_id": "manual", "alias": "user-declared", "gateway": "manual",
        "routing_mode": "user_declared", "status": "enabled", "last_verified_at": None,
        "acquisition_mode": "manual", "app_name": None, "configured_model_id": None,
        "model_family": None, "capabilities": ["text", "manual_import"],
        "pricing_status": "manual", "privacy_profile": "local_only", "pricing_version": None,
    }
    assert providers["google"]["status"] == "disabled"
    assert providers["google"]["configured_model_id"] is None
    assert providers["google"]["model_family"] is None
    for target in run["targets"]:
        data = {"target_id":target["target_id"], "content":"  原文\n"+target["model_id"], "model_family":"unknown"}
        with ThreadPoolExecutor(max_workers=2) as pool:
            res = list(pool.map(lambda _:client.post(path+"/manual-responses", json=data), range(2)))
        assert all(r.status_code == 201 for r in res)
        assert res[0].json()["response_id"] == res[1].json()["response_id"]
        assert client.post(path+"/manual-responses", json=data | {"content":"edited"}).status_code == 409
    assert client.get(path).json()["status"] == "complete"
    rows = client.get(path+"/responses").json()
    assert len(rows) == 2
    assert all(r["identity_confidence"] == "user_declared" and r["content"].startswith("  原文\n") for r in rows)
    assert all(r["resolved_provider_id"] is None and r["resolved_model_id"] is None for r in rows)
    assert all(r["attempt_no"] == 0 and r["inclusion"] == "included" for r in rows)


def test_disabled_provider_is_visible_but_cannot_create_business_rows(client, thread):
    with connect() as conn:
        before_runs = conn.execute("SELECT count(*) AS count FROM runs").fetchone()["count"]
        before_messages = conn.execute("SELECT count(*) AS count FROM messages").fetchone()["count"]
    response = client.post("/v1/runs", headers={"Idempotency-Key": str(uuid4())}, json={
        "conversation_id": thread["conversation_id"],
        "question": "This must not dispatch",
        "model_targets": [{"provider": "google", "model_id": "gemini-api-candidate"}],
    })
    assert response.status_code == 422
    with connect() as conn:
        assert conn.execute("SELECT count(*) AS count FROM runs").fetchone()["count"] == before_runs
        assert conn.execute("SELECT count(*) AS count FROM messages").fetchone()["count"] == before_messages


def test_catalog_edit_does_not_relabel_target_or_original(client, thread):
    run = start(client, thread)
    target = run["targets"][0]
    path = f"/v1/runs/{run['run_id']}"
    assert client.post(path + "/manual-responses", json={
        "target_id": target["target_id"], "content": "identity snapshot",
        "model_family": "declared-family",
    }).status_code == 201
    before = client.get(path + "/responses").json()[0]
    with connect() as conn:
        snapshot = conn.execute("""SELECT registry_status, acquisition_mode, model_family,
            identity_confidence, registry_verified_at FROM run_targets WHERE target_id=%s""",
            (target["target_id"],)).fetchone()
        conn.execute("""UPDATE provider_models SET status='disabled', app_name='Changed catalog label'
            WHERE provider_id='manual' AND alias='user-declared'""")
    try:
        after = client.get(path + "/responses").json()[0]
        assert after == before
        assert snapshot == {
            "registry_status": "enabled", "acquisition_mode": "manual",
            "model_family": None, "identity_confidence": "user_declared",
            "registry_verified_at": None,
        }
    finally:
        with connect() as conn:
            conn.execute("""UPDATE provider_models SET status='enabled', app_name=NULL
                WHERE provider_id='manual' AND alias='user-declared'""")


def test_expired_manual_target_preserves_original(client, thread):
    run = start(client, thread)
    path = f"/v1/runs/{run['run_id']}"
    assert client.post(path+"/manual-responses", json={"target_id":str(uuid4()), "content":"wrong"}).status_code == 404
    assert client.post(path+"/manual-responses", json={"target_id":run["targets"][0]["target_id"], "content":"original"}).status_code == 201
    with connect() as conn:
        conn.execute("UPDATE runs SET deadline=now()-interval '1 minute' WHERE run_id=%s", (run["run_id"],))
    assert client.get(path).json()["status"] == "partial_complete"
    assert client.post(path+"/manual-responses", json={"target_id":run["targets"][1]["target_id"], "content":"late"}).status_code == 409
    assert len(client.get(path+"/responses").json()) == 1
    assert client.get(f"/v1/runs/{uuid4()}/responses").status_code == 404


def test_normalized_replay_defaults_and_context_order_are_stable(client, thread):
    source_ids = []
    for content in ("First selected source", "Second selected source"):
        source_ids.append(client.post(
            f"/v1/conversations/{thread['conversation_id']}/messages",
            json={"content": content},
        ).json()["message_id"])
    key = str(uuid4())
    body = {
        "conversation_id": thread["conversation_id"],
        "question": "Normalized request",
        "model_targets": [{"provider": "manual", "model_id": "Manual A"}],
        "context_message_ids": source_ids,
    }
    created = client.post("/v1/runs", headers={"Idempotency-Key": key}, json=body)
    assert created.status_code == 202
    explicit_defaults = client.post("/v1/runs", headers={"Idempotency-Key": key}, json={
        **body, "deadline_seconds": 86400, "context_message_ids": source_ids,
    })
    assert explicit_defaults.status_code == 202
    assert explicit_defaults.json()["run_id"] == created.json()["run_id"]
    reversed_sources = client.post("/v1/runs", headers={"Idempotency-Key": key}, json={
        **body, "context_message_ids": list(reversed(source_ids)),
    })
    assert reversed_sources.status_code == 409
    with connect() as conn:
        stored = conn.execute(
            """SELECT request_schema_version,normalized_request FROM runs
                WHERE run_id=%s""", (created.json()["run_id"],),
        ).fetchone()
        selected = conn.execute(
            """SELECT message_id FROM run_context_sources WHERE run_id=%s
                ORDER BY position""", (created.json()["run_id"],),
        ).fetchall()
    assert stored["request_schema_version"] == 1
    assert stored["normalized_request"]["deadline_seconds"] == 86400
    assert [str(row["message_id"]) for row in selected] == source_ids
    assert client.post("/v1/runs", headers={"Idempotency-Key": str(uuid4())}, json={
        **body, "max_cost_microusd": None,
    }).status_code == 422
    assert client.post("/v1/runs", headers={"Idempotency-Key": str(uuid4())}, json={
        **body, "max_cost_micro_usd": 10,
    }).status_code == 422


def test_legacy_run_key_replays_only_with_legacy_defaults(client, thread):
    key = str(uuid4())
    body = {
        "conversation_id": thread["conversation_id"],
        "question": "Legacy replay",
        "model_targets": [{"provider": "manual", "model_id": "Legacy model"}],
    }
    created = client.post("/v1/runs", headers={"Idempotency-Key": key}, json=body)
    assert created.status_code == 202
    legacy = LegacyStart(
        conversation_id=thread["conversation_id"], question=body["question"],
        model_targets=[Target(**body["model_targets"][0])],
    )
    with connect() as conn:
        conn.execute(
            """UPDATE runs SET request_schema_version=0,normalized_request=NULL,
                request_hash=%s WHERE run_id=%s""",
            (digest(legacy.model_dump_json()), created.json()["run_id"]),
        )
    assert client.post(
        "/v1/runs", headers={"Idempotency-Key": key}, json=body,
    ).status_code == 202
    assert client.post(
        "/v1/runs", headers={"Idempotency-Key": key},
        json={**body, "deadline_seconds": 60},
    ).status_code == 409
