from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from app.db import connect


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
    assert client.get("/v1/providers").json()[0]["provider_id"] == "manual"
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
