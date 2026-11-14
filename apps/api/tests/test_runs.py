from concurrent.futures import ThreadPoolExecutor
import hashlib
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest

from app.db import connect
from app.runs import LegacyStart, Target
from app.security import digest
from app.worker import RunWorker


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
    assert run["state"] == "queued"
    assert run["project_id"] == thread["project_id"]
    assert run["comparison_id"] is None
    assert run["error_code"] is None
    assert set(run["links"]) == {"status", "responses", "report", "events"}
    assert all(target["state"] == "awaiting_manual" for target in run["targets"])
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
    for position, target in enumerate(run["targets"]):
        content = "  Exact CRLF\r\n原文\n" + target["model_id"]
        data = {
            "target_id": target["target_id"],
            "content": content,
            "model_family": "unknown",
            "declared_app": "Fixture Chat" if position else None,
        }
        if position:
            data["declared_model_id"] = "Declared fixture model"
        barrier = Barrier(2)

        def paste(_):
            barrier.wait()
            return client.post(path + "/manual-responses", json=data)

        with ThreadPoolExecutor(max_workers=2) as pool:
            res = list(pool.map(paste, range(2)))
        assert all(r.status_code == 201 for r in res)
        assert res[0].json()["response_id"] == res[1].json()["response_id"]
        original = res[0].json()
        assert original["content"] == content
        assert original["source_hash"] == hashlib.sha256(content.encode()).hexdigest()
        assert original["run_id"] == run["run_id"]
        assert original["provider"] == "manual"
        assert original["requested_model_id"] == target["model_id"]
        assert original["actual_model_id"] == data.get(
            "declared_model_id", target["model_id"]
        )
        assert original["declared_model_id"] == original["actual_model_id"]
        assert original["declared_app"] == data["declared_app"]
        assert original["resolved_provider_id"] is None
        assert original["resolved_model_id"] is None
        assert original["elapsed_ms"] is None
        assert original["input_tokens"] is None
        assert original["output_tokens"] is None
        assert original["actual_cost_microusd"] is None
        assert original["attempt_no"] == 0
        assert original["context_snapshot_id"] is None
        assert original["inclusion"] == "included"
        assert client.post(path+"/manual-responses", json=data | {"content":"edited"}).status_code == 409
        assert client.post(
            path + "/manual-responses",
            json=data | {"model_family": "changed-family"},
        ).status_code == 409
        assert client.post(
            path + "/manual-responses",
            json=data | {"declared_app": "Changed App"},
        ).status_code == 409
        assert client.post(
            path + "/manual-responses",
            json=data | {"declared_model_id": "Changed model"},
        ).status_code == 409
        with connect() as conn:
            event_count = conn.execute(
                """SELECT count(*) AS count FROM audit_events
                   WHERE action='manual_original_imported' AND resource_id=%s""",
                (original["response_id"],),
            ).fetchone()["count"]
        assert event_count == 1
    collected = client.get(path).json()
    assert collected["status"] == "running"
    assert collected["state"] == "synthesizing"
    assert all(target["state"] == "succeeded" for target in collected["targets"])
    rows = client.get(path+"/responses").json()
    assert len(rows) == 2
    assert all(
        r["identity_confidence"] == "user_declared"
        and r["content"].startswith("  Exact CRLF\r\n原文\n")
        for r in rows
    )
    assert all(r["resolved_provider_id"] is None and r["resolved_model_id"] is None for r in rows)
    assert all(r["attempt_no"] == 0 and r["inclusion"] == "included" for r in rows)
    first_page = client.get(path + "/events", params={"limit": 4}).json()
    assert [item["sequence"] for item in first_page["items"]] == [1, 2, 3, 4]
    second_page = client.get(
        path + "/events", params={"after": first_page["next_after"], "limit": 100}
    ).json()
    events = first_page["items"] + second_page["items"]
    assert [item["sequence"] for item in events] == list(range(1, 10))
    assert [item["kind"] for item in events].count("original_saved") == 2
    assert [item["state"] for item in events if item["kind"] == "run_state"] == [
        "queued",
        "running",
        "synthesizing",
    ]
    assert client.get(
        path + "/events", params={"after": second_page["next_after"]}
    ).json() == {"items": [], "next_after": 9}


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
    original_data = {
        "target_id": run["targets"][0]["target_id"],
        "content": "original",
        "declared_app": "Manual fixture",
    }
    created = client.post(path+"/manual-responses", json=original_data)
    assert created.status_code == 201
    with connect() as conn:
        conn.execute("UPDATE runs SET deadline=now()-interval '1 minute' WHERE run_id=%s", (run["run_id"],))
    expired = client.get(path).json()
    assert expired["status"] == "running"
    assert expired["state"] == "synthesizing"
    assert {target["state"] for target in expired["targets"]} == {
        "succeeded",
        "timed_out",
    }
    replay = client.post(path+"/manual-responses", json=original_data)
    assert replay.status_code == 201
    assert replay.json()["response_id"] == created.json()["response_id"]
    assert client.post(
        path + "/manual-responses",
        json=original_data | {"declared_app": "Edited declaration"},
    ).status_code == 409
    assert client.post(path+"/manual-responses", json={"target_id":run["targets"][1]["target_id"], "content":"late"}).status_code == 409
    assert len(client.get(path+"/responses").json()) == 1
    assert client.get(f"/v1/runs/{uuid4()}/responses").status_code == 404


def test_cancel_is_idempotent_and_freezes_run(client, thread):
    run = start(client, thread)
    path = f"/v1/runs/{run['run_id']}"
    cancelled = client.post(path + "/cancel")
    assert cancelled.status_code == 200
    body = cancelled.json()
    assert body["state"] == "cancelled"
    assert body["status"] == "failed"
    assert body["error_code"] == "cancelled"
    assert all(target["state"] == "cancelled" for target in body["targets"])
    replay = client.post(path + "/cancel")
    assert replay.status_code == 200
    assert replay.json()["state"] == "cancelled"
    target = run["targets"][0]
    assert client.post(
        path + "/manual-responses",
        json={"target_id": target["target_id"], "content": "too late"},
    ).status_code == 409
    events = client.get(path + "/events").json()["items"]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert events[-1]["kind"] == "run_state"
    assert events[-1]["state"] == "cancelled"
    with connect() as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.transaction():
                conn.execute(
                    """UPDATE runs SET state='running',revision=revision+1,
                              terminal_at=NULL,error_code=NULL WHERE run_id=%s""",
                    (run["run_id"],),
                )


def test_worker_leases_and_parks_manual_run_once(client, thread):
    run = start(client, thread)
    worker = RunWorker("fixture-worker", lease_seconds=10)
    for _ in range(20):
        worker.run_once()
        parked = client.get(f"/v1/runs/{run['run_id']}").json()
        if parked["state"] == "awaiting_manual":
            break
    assert parked["state"] == "awaiting_manual"
    assert parked["status"] == "awaiting_manual"
    with connect() as conn:
        work = conn.execute(
            "SELECT * FROM run_work WHERE run_id=%s", (run["run_id"],)
        ).fetchone()
    assert work["state"] == "waiting"
    assert work["fence"] == 1
    assert work["lease_token"] is None
    assert work["lease_expires_at"] is None
    assert work["worker_id"] is None
    assert worker.run_once() is False
    states = [
        event["state"]
        for event in client.get(f"/v1/runs/{run['run_id']}/events").json()["items"]
        if event["kind"] == "run_state"
    ]
    assert states == ["queued", "running", "awaiting_manual"]


def test_manual_import_hides_foreign_run_and_rejects_official_target(client, thread):
    run = start(client, thread)
    path = f"/v1/runs/{run['run_id']}"
    with connect() as conn:
        provider = "fixture-provider-" + uuid4().hex
        conn.execute(
            """INSERT INTO provider_models (
                   provider_id,alias,gateway,routing_mode,status,last_verified_at,
                   acquisition_mode,app_name,configured_model_id,model_family,
                   capabilities,pricing_status,privacy_profile,pricing_version,
                   identity_confidence
               ) VALUES (%s,'official','fixture-gateway','direct','enabled',now(),
                         'official_api','Fixture API','fixture-model','Fixture Family',
                         ARRAY['text'],'verified_free','allowlisted','fixture-price-v1',
                         'provider_reported')""",
            (provider,),
        )
        official_target = conn.execute(
            """INSERT INTO run_targets (
                   run_id,provider,alias,model_id,gateway,routing_mode
               ) VALUES (%s,%s,'official','fixture-model','fixture-gateway','direct')
               RETURNING target_id""",
            (run["run_id"], provider),
        ).fetchone()["target_id"]
        official_content = "existing official response"
        conn.execute(
            """INSERT INTO model_responses (
                   target_id,actual_model_id,model_family,identity_confidence,
                   acquisition_mode,content,source_hash,resolved_provider_id,
                   resolved_model_id
               ) VALUES (%s,'fixture-model','Fixture Family','provider_reported',
                         'official_api',%s,%s,%s,'fixture-model')""",
            (
                official_target,
                official_content,
                hashlib.sha256(official_content.encode()).hexdigest(),
                provider,
            ),
        )

        foreign_owner = conn.execute(
            """INSERT INTO users (login,password_hash) VALUES (%s,'unused')
               RETURNING user_id""",
            ("foreign-" + uuid4().hex,),
        ).fetchone()["user_id"]
        foreign_project = conn.execute(
            """INSERT INTO projects (owner_id,name) VALUES (%s,'Foreign')
               RETURNING project_id""",
            (foreign_owner,),
        ).fetchone()["project_id"]
        foreign_conversation = conn.execute(
            """INSERT INTO conversations (project_id,title) VALUES (%s,'Foreign')
               RETURNING conversation_id""",
            (foreign_project,),
        ).fetchone()["conversation_id"]
        foreign_content = "Foreign question"
        foreign_message = conn.execute(
            """INSERT INTO messages (
                   conversation_id,sequence,role,content,source_hash
               ) VALUES (%s,1,'user',%s,%s) RETURNING message_id""",
            (
                foreign_conversation,
                foreign_content,
                hashlib.sha256(foreign_content.encode()).hexdigest(),
            ),
        ).fetchone()["message_id"]
        foreign_run = conn.execute(
            """INSERT INTO runs (
                   project_id,conversation_id,message_id,owner_id,request_key,
                   request_hash,deadline
               ) VALUES (%s,%s,%s,%s,%s,'foreign',now()+interval '1 hour')
               RETURNING run_id""",
            (
                foreign_project,
                foreign_conversation,
                foreign_message,
                foreign_owner,
                "foreign-" + uuid4().hex,
            ),
        ).fetchone()["run_id"]
        foreign_target = conn.execute(
            """INSERT INTO run_targets (
                   run_id,provider,alias,model_id,gateway,routing_mode
               ) VALUES (%s,'manual','user-declared','Foreign model','manual',
                         'user_declared') RETURNING target_id""",
            (foreign_run,),
        ).fetchone()["target_id"]

    wrong_kind = client.post(
        path + "/manual-responses",
        json={
            "target_id": str(official_target),
            "content": official_content,
            "model_family": "Fixture Family",
        },
    )
    assert wrong_kind.status_code == 409
    foreign = client.post(
        f"/v1/runs/{foreign_run}/manual-responses",
        json={"target_id": str(foreign_target), "content": "must stay hidden"},
    )
    assert foreign.status_code == 404
    assert client.post(
        path + "/manual-responses",
        json={
            "target_id": run["targets"][0]["target_id"],
            "content": "unknown field",
            "unexpected": True,
        },
    ).status_code == 422


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
