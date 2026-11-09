from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.contracts import NewMessage, OriginalDetails, Provider, Run, StoredOriginal
from app.security import audit, digest, principal, transaction
from app.workspace import conversation, insert_message

router = APIRouter(prefix="/v1")


class Target(BaseModel):
    provider: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=160, pattern=r"\S")


class Start(BaseModel):
    conversation_id: UUID
    question: str = Field(min_length=1, max_length=64000, pattern=r"\S")
    model_targets: list[Target] = Field(min_length=1, max_length=12)

    @field_validator("model_targets")
    @classmethod
    def distinct_targets(cls, targets):
        if len({(t.provider, t.model_id.strip().casefold()) for t in targets}) != len(targets):
            raise ValueError("Select distinct targets")
        return targets


class Original(NewMessage):
    target_id: UUID
    model_family: str = Field(default="unknown", min_length=1, max_length=160, pattern=r"\S")


def run_record(conn, run_id, owner):
    row = conn.execute("SELECT run_id, conversation_id, message_id, created_at, deadline FROM runs WHERE run_id=%s AND owner_id=%s",
                       (run_id, owner)).fetchone()
    if not row:
        raise HTTPException(404, "Run not found")
    return row


def summary(conn, row):
    targets = conn.execute("""
        SELECT t.target_id, t.provider, t.model_id, t.gateway, t.routing_mode, m.response_id
        FROM run_targets t LEFT JOIN model_responses m USING (target_id)
        WHERE t.run_id=%s ORDER BY t.model_id""", (row["run_id"],)).fetchall()
    expired = datetime.now(timezone.utc) >= row["deadline"]
    for target in targets:
        target["status"] = "complete" if target["response_id"] else ("missing" if expired else "awaiting_manual")
    if all(t["response_id"] for t in targets):
        status = "complete"
    elif expired:
        status = "partial_complete" if any(t["response_id"] for t in targets) else "failed"
    else:
        status = "awaiting_manual"
    return {**row, "status": status, "targets": targets, "links": {"status": f"/v1/runs/{row['run_id']}"}}


@router.get("/providers", response_model=list[Provider])
def providers(owner=Depends(principal), conn=Depends(transaction)):
    return conn.execute("SELECT * FROM provider_models ORDER BY provider_id, alias").fetchall()


@router.post("/runs", response_model=Run, status_code=202)
def start(data: Start, request: Request, idempotency_key: str = Header(min_length=1, max_length=128),
          owner=Depends(principal), conn=Depends(transaction)):
    fingerprint = digest(data.model_dump_json())
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"{owner}:{idempotency_key}",))
    existing = conn.execute("SELECT request_hash, run_id FROM runs WHERE owner_id=%s AND request_key=%s",
                            (owner, idempotency_key)).fetchone()
    if existing:
        if existing["request_hash"] != fingerprint:
            raise HTTPException(409, "Key already used for a different run request")
        return summary(conn, run_record(conn, existing["run_id"], owner))
    conversation(conn, data.conversation_id, owner, lock=True)
    registry = conn.execute("SELECT * FROM provider_models WHERE provider_id='manual' AND status='enabled'").fetchone()
    if not registry or any(t.provider != registry["provider_id"] for t in data.model_targets):
        raise HTTPException(422, "Select an enabled manual target")
    message = insert_message(conn, data.conversation_id, data.question)
    row = conn.execute("""
        INSERT INTO runs (conversation_id,message_id,owner_id,request_key,request_hash)
        VALUES (%s,%s,%s,%s,%s) RETURNING run_id
    """, (data.conversation_id, message["message_id"], owner, idempotency_key, fingerprint)).fetchone()
    for target in data.model_targets:
        conn.execute("""
            INSERT INTO run_targets (run_id,provider,alias,model_id,gateway,routing_mode)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (row["run_id"], registry["provider_id"], registry["alias"], target.model_id.strip(),
              registry["gateway"], registry["routing_mode"]))
    audit(conn, "run_created", request.state.trace, owner, row["run_id"])
    return summary(conn, run_record(conn, row["run_id"], owner))


@router.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: UUID, owner=Depends(principal), conn=Depends(transaction)):
    return summary(conn, run_record(conn, run_id, owner))


@router.get("/conversations/{conversation_id}/runs", response_model=list[Run])
def list_runs(conversation_id: UUID, owner=Depends(principal), conn=Depends(transaction)):
    conversation(conn, conversation_id, owner)
    rows = conn.execute("""
        SELECT run_id, conversation_id, message_id, created_at, deadline FROM runs
        WHERE conversation_id=%s AND owner_id=%s ORDER BY created_at, run_id
    """, (conversation_id, owner)).fetchall()
    return [summary(conn, row) for row in rows]


def response_rows(conn, run_id):
    return conn.execute("""
        SELECT m.*, t.run_id, t.provider, t.model_id AS requested_model_id, t.gateway, t.routing_mode
        FROM model_responses m JOIN run_targets t USING (target_id)
        WHERE t.run_id=%s ORDER BY m.created_at, m.response_id""", (run_id,)).fetchall()


@router.get("/runs/{run_id}/responses", response_model=list[OriginalDetails])
def originals(run_id: UUID, owner=Depends(principal), conn=Depends(transaction)):
    run_record(conn, run_id, owner)
    return response_rows(conn, run_id)


@router.post("/runs/{run_id}/manual-responses", response_model=StoredOriginal, status_code=201)
def import_original(run_id: UUID, data: Original, request: Request, owner=Depends(principal), conn=Depends(transaction)):
    run = run_record(conn, run_id, owner)
    target = conn.execute("SELECT * FROM run_targets WHERE run_id=%s AND target_id=%s FOR UPDATE",
                          (run_id, data.target_id)).fetchone()
    if not target:
        raise HTTPException(404, "Run target not found")
    existing = conn.execute("SELECT * FROM model_responses WHERE target_id=%s", (data.target_id,)).fetchone()
    if existing:
        if (existing["content"], existing["model_family"]) != (data.content, data.model_family):
            raise HTTPException(409, "This target already has an immutable original")
        return existing
    if datetime.now(timezone.utc) >= run["deadline"]:
        raise HTTPException(409, "This run has reached its deadline")
    row = conn.execute("""
        INSERT INTO model_responses (target_id,actual_model_id,model_family,identity_confidence,
            acquisition_mode,content,source_hash) VALUES (%s,%s,%s,'user_declared','manual',%s,%s) RETURNING *
    """, (data.target_id, target["model_id"], data.model_family, data.content, digest(data.content))).fetchone()
    audit(conn, "manual_original_imported", request.state.trace, owner, row["response_id"])
    return row
