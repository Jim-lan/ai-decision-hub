from datetime import datetime, timezone
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts import (
    NewMessage,
    OriginalDetails,
    Provider,
    Run,
    StoredOriginal,
    Usage,
    UsageWindow,
)
from app.security import audit, digest, principal, transaction
from app.workspace import conversation, insert_message

router = APIRouter(prefix="/v1")


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=160, pattern=r"\S")


class Start(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    question: str = Field(min_length=1, max_length=64000, pattern=r"\S")
    model_targets: list[Target] = Field(min_length=1, max_length=12)
    context_message_ids: list[UUID] = Field(
        default_factory=list, max_length=32, json_schema_extra={"uniqueItems": True},
    )
    deadline_seconds: int = Field(default=86400, ge=1, le=86400)
    max_cost_microusd: int = Field(default=None, ge=0)  # type: ignore[assignment]

    @field_validator("model_targets")
    @classmethod
    def distinct_targets(cls, targets):
        if len({(t.provider, t.model_id.strip().casefold()) for t in targets}) != len(targets):
            raise ValueError("Select distinct targets")
        return targets

    @field_validator("context_message_ids")
    @classmethod
    def distinct_context_sources(cls, sources):
        if len(sources) != len(set(sources)):
            raise ValueError("Select distinct context messages")
        return sources


class LegacyStart(BaseModel):
    conversation_id: UUID
    question: str = Field(min_length=1, max_length=64000, pattern=r"\S")
    model_targets: list[Target] = Field(min_length=1, max_length=12)


class Original(NewMessage):
    target_id: UUID
    model_family: str = Field(default="unknown", min_length=1, max_length=160, pattern=r"\S")


def run_record(conn, run_id, owner):
    row = conn.execute("SELECT run_id, project_id, conversation_id, message_id, created_at, deadline FROM runs WHERE run_id=%s AND owner_id=%s",
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
    return conn.execute("""SELECT provider_id, alias, gateway, routing_mode, status,
        last_verified_at, acquisition_mode, app_name, configured_model_id, model_family,
        capabilities, pricing_status, privacy_profile, pricing_version
        FROM provider_models ORDER BY (status = 'enabled') DESC, provider_id, alias""").fetchall()


@router.post("/runs", response_model=Run, status_code=202)
def start(data: Start, request: Request, idempotency_key: str = Header(min_length=1, max_length=128),
          owner=Depends(principal), conn=Depends(transaction)):
    normalized = data.model_dump(mode="json")
    normalized_json = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    fingerprint = digest(normalized_json)
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"{owner}:{idempotency_key}",))
    existing = conn.execute("""SELECT request_hash,request_schema_version,run_id
        FROM runs WHERE owner_id=%s AND request_key=%s""",
                            (owner, idempotency_key)).fetchone()
    if existing:
        if existing["request_schema_version"] == 0:
            legacy_defaults = (
                not data.context_message_ids
                and data.deadline_seconds == 86400
                and data.max_cost_microusd is None
            )
            legacy = LegacyStart(
                conversation_id=data.conversation_id,
                question=data.question,
                model_targets=data.model_targets,
            )
            replay_matches = legacy_defaults and existing["request_hash"] == digest(
                legacy.model_dump_json()
            )
        else:
            replay_matches = existing["request_hash"] == fingerprint
        if not replay_matches:
            raise HTTPException(409, "Key already used for a different run request")
        return summary(conn, run_record(conn, existing["run_id"], owner))
    thread = conversation(conn, data.conversation_id, owner, lock=True)
    registry = conn.execute("SELECT * FROM provider_models WHERE provider_id='manual' AND status='enabled'").fetchone()
    if not registry or any(t.provider != registry["provider_id"] for t in data.model_targets):
        raise HTTPException(422, "Select an enabled manual target")
    if data.context_message_ids:
        selected = conn.execute("""SELECT m.message_id FROM messages m
            JOIN conversations c USING (conversation_id)
            WHERE c.project_id=%s AND m.message_id=ANY(%s::uuid[])""",
            (thread["project_id"], data.context_message_ids)).fetchall()
        if {row["message_id"] for row in selected} != set(data.context_message_ids):
            raise HTTPException(404, "Context message not found")
    message = insert_message(conn, data.conversation_id, data.question)
    row = conn.execute("""
        INSERT INTO runs (
            project_id,conversation_id,message_id,owner_id,request_key,request_hash,
            request_schema_version,normalized_request,max_cost_microusd,deadline
        ) VALUES (%s,%s,%s,%s,%s,%s,1,%s::jsonb,%s,
                  now() + (%s * interval '1 second')) RETURNING run_id
    """, (thread["project_id"], data.conversation_id, message["message_id"], owner,
          idempotency_key, fingerprint, normalized_json, data.max_cost_microusd,
          data.deadline_seconds)).fetchone()
    for position, source_id in enumerate(data.context_message_ids, start=1):
        conn.execute("""INSERT INTO run_context_sources (run_id,position,message_id)
            VALUES (%s,%s,%s)""", (row["run_id"], position, source_id))
    for target in data.model_targets:
        conn.execute("""
            INSERT INTO run_targets (
                run_id, provider, alias, model_id, gateway, routing_mode,
                registry_status, acquisition_mode, app_name, configured_model_id,
                model_family, capabilities, pricing_status, privacy_profile,
                pricing_version, identity_confidence, registry_verified_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (row["run_id"], registry["provider_id"], registry["alias"], target.model_id.strip(),
              registry["gateway"], registry["routing_mode"], registry["status"],
              registry["acquisition_mode"], registry["app_name"], registry["configured_model_id"],
              registry["model_family"], registry["capabilities"], registry["pricing_status"],
              registry["privacy_profile"], registry["pricing_version"],
              registry["identity_confidence"], registry["last_verified_at"]))
    audit(conn, "run_created", request.state.trace, owner, row["run_id"],
          project=thread["project_id"])
    return summary(conn, run_record(conn, row["run_id"], owner))


def _usage_window(conn, owner, cap, predicate, params):
    row = conn.execute(f"""SELECT
        COALESCE(sum(amount_microusd) FILTER (WHERE state='reserved' AND ({predicate})),0)
            AS reserved_microusd,
        COALESCE(sum(greatest(amount_microusd,coalesce(actual_cost_microusd,0)))
            FILTER (WHERE state='held' AND ({predicate})),0) AS held_microusd,
        COALESCE(sum(actual_cost_microusd)
            FILTER (WHERE state='settled' AND ({predicate})),0) AS settled_microusd,
        count(*) FILTER (WHERE state<>'released' AND ({predicate})) AS relevant_count,
        count(*) FILTER (WHERE state<>'released' AND ({predicate})
            AND (state IN ('reserved','held') OR input_tokens IS NULL OR output_tokens IS NULL))
            AS unknown_count,
        COALESCE(sum(input_tokens) FILTER (WHERE state='settled' AND ({predicate})),0)
            AS input_tokens,
        COALESCE(sum(output_tokens) FILTER (WHERE state='settled' AND ({predicate})),0)
            AS output_tokens
        FROM budget_reservations WHERE owner_id=%s""", (*params,) * 7 + (owner,)).fetchone()
    unknown = row.pop("unknown_count") > 0
    row.pop("relevant_count")
    if unknown:
        row["input_tokens"] = row["output_tokens"] = None
    return UsageWindow(cap_microusd=cap, **row)


@router.get("/usage", response_model=Usage)
def usage(run_id: UUID | None = None, owner=Depends(principal), conn=Depends(transaction)):
    as_of = datetime.now(timezone.utc)
    policy = conn.execute("""SELECT run_cap_microusd,day_cap_microusd,month_cap_microusd
        FROM owner_budget_policies WHERE owner_id=%s""", (owner,)).fetchone()
    if not policy:
        raise HTTPException(503, "Budget policy unavailable")
    day = _usage_window(
        conn, owner, policy["day_cap_microusd"],
        "state='held' OR owner_day=%s", (as_of.date(),),
    )
    month = _usage_window(
        conn, owner, policy["month_cap_microusd"],
        "state='held' OR owner_month=%s", (as_of.date().replace(day=1),),
    )
    run_window = None
    if run_id is not None:
        if not conn.execute(
            "SELECT 1 FROM runs WHERE run_id=%s AND owner_id=%s", (run_id, owner),
        ).fetchone():
            raise HTTPException(404, "Run not found")
        run_window = _usage_window(
            conn, owner, policy["run_cap_microusd"], "run_id=%s", (run_id,),
        )
    return Usage(currency="USD", as_of=as_of, day=day, month=month, run=run_window)


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
    audit(conn, "manual_original_imported", request.state.trace, owner, row["response_id"],
          project=run["project_id"])
    return row
