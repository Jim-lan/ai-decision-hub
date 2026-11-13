import base64
import binascii
from datetime import datetime, timezone
import hmac
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.adapters.postgres_conversations import PostgresConversationRepository
from app.contracts import (
    Conversation,
    History,
    Message,
    Named,
    NewConversation,
    NewMessage,
    Project,
    SearchPage,
)
from app.db import read_secret
from app.ports import ConversationRepository, RepositoryNotFound
from app.security import audit, digest, principal, transaction

router = APIRouter(prefix="/v1")


def repository(conn) -> ConversationRepository:
    """Compose the infrastructure adapter at the application boundary."""
    return PostgresConversationRepository(conn)


def cursor_key() -> bytes:
    key = read_secret("CURSOR_SIGNING_KEY").encode()
    if len(key) < 32:
        raise ValueError("Use at least 32 bytes for the cursor signing key")
    return key


def encode_cursor(data):
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.digest(cursor_key(), raw, "sha256")
    return ".".join(
        base64.urlsafe_b64encode(part).decode() for part in (raw, signature)
    )


def decode_cursor(cursor):
    try:
        payload, signature = cursor.split(".")
        raw = base64.b64decode(payload, altchars=b"-_", validate=True)
        actual = base64.b64decode(signature, altchars=b"-_", validate=True)
        expected = hmac.digest(cursor_key(), raw, "sha256")
        if not hmac.compare_digest(actual, expected):
            raise ValueError
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError):
        raise HTTPException(400, "Invalid history cursor") from None


def require_project(conn, project_id, owner):
    try:
        return repository(conn).get_project(project_id, owner)
    except RepositoryNotFound:
        raise HTTPException(404, "Project not found")


def conversation(conn, conversation_id, owner, *, lock=False):
    try:
        return repository(conn).get_conversation(
            conversation_id, owner, lock=lock,
        )
    except RepositoryNotFound:
        raise HTTPException(404, "Conversation not found")


def insert_message(conn, conversation_id, content):
    return repository(conn).append_message(conversation_id, content)


@router.post("/projects", response_model=Project, status_code=201)
def create_project(data: Named, request: Request, owner=Depends(principal), conn=Depends(transaction)):
    row = repository(conn).create_project(owner, data.name)
    audit(conn, "project_created", request.state.trace, owner, row["project_id"],
          project=row["project_id"])
    return row


@router.get("/projects", response_model=list[Project])
def projects(owner=Depends(principal), conn=Depends(transaction)):
    return repository(conn).list_projects(owner)


@router.get("/projects/{project_id}", response_model=Project)
def project(project_id: UUID, owner=Depends(principal), conn=Depends(transaction)):
    return require_project(conn, project_id, owner)


@router.post("/conversations", response_model=Conversation, status_code=201)
def create_conversation(data: NewConversation, request: Request, owner=Depends(principal), conn=Depends(transaction)):
    require_project(conn, data.project_id, owner)
    row = repository(conn).create_conversation(
        data.project_id, data.title.strip(),
    )
    audit(conn, "conversation_created", request.state.trace, owner, row["conversation_id"],
          project=data.project_id)
    return row


@router.get("/projects/{project_id}/conversations", response_model=list[Conversation])
def conversations(project_id: UUID, owner=Depends(principal), conn=Depends(transaction)):
    require_project(conn, project_id, owner)
    return repository(conn).list_conversations(project_id)


@router.get("/conversations/{conversation_id}", response_model=Conversation)
def get_conversation(conversation_id: UUID, owner=Depends(principal), conn=Depends(transaction)):
    return conversation(conn, conversation_id, owner)


@router.post("/conversations/{conversation_id}/messages", response_model=Message, status_code=201)
def append(conversation_id: UUID, data: NewMessage, request: Request, owner=Depends(principal), conn=Depends(transaction)):
    thread = conversation(conn, conversation_id, owner, lock=True)
    item = insert_message(conn, conversation_id, data.content)
    audit(conn, "message_appended", request.state.trace, owner, item["message_id"],
          project=thread["project_id"])
    return item


@router.get("/conversations/{conversation_id}/messages", response_model=History)
def history(conversation_id: UUID, cursor: str | None = None, limit: int = Query(50, ge=1, le=100),
            owner=Depends(principal), conn=Depends(transaction)):
    conversation(conn, conversation_id, owner)
    sequence = 0
    if cursor is not None:
        try:
            resource, position = base64.b64decode(cursor, altchars=b"-_", validate=True).decode().split(":")
            sequence = int(position)
            if resource != str(conversation_id) or not 0 <= sequence < 2**63:
                raise ValueError
        except (ValueError, binascii.Error):
            raise HTTPException(400, "Invalid history cursor") from None
    rows = repository(conn).list_messages(
        conversation_id, sequence, limit + 1,
    )
    cursor_out = None
    if len(rows) > limit:
        key = f"{conversation_id}:{rows[limit-1]['sequence']}"
        cursor_out = base64.urlsafe_b64encode(key.encode()).decode()
    return {"items": rows[:limit], "next_cursor": cursor_out}


@router.get("/projects/{project_id}/history", response_model=SearchPage)
def search_history(
    project_id: UUID,
    q: str = Query(min_length=1, max_length=160, pattern=r"\S"),
    cursor: str | None = Query(default=None, max_length=1024),
    limit: int = Query(50, ge=1, le=100),
    owner=Depends(principal),
    conn=Depends(transaction),
):
    require_project(conn, project_id, owner)
    after_created = datetime.min.replace(tzinfo=timezone.utc)
    after_kind = ""
    after_resource = UUID(int=0)
    if cursor is not None:
        data = decode_cursor(cursor)
        try:
            if set(data) != {"project", "query", "created", "kind", "resource"}:
                raise ValueError
            if not all(isinstance(value, str) for value in data.values()):
                raise ValueError
            after_created = datetime.fromisoformat(data["created"])
            after_kind = data["kind"]
            after_resource = UUID(data["resource"])
            if after_created.tzinfo is None:
                raise ValueError
            if data["project"] != str(project_id) or data["query"] != digest(q):
                raise ValueError
            anchor = repository(conn).has_search_anchor(
                project_id, after_resource, after_created, q,
            )
            if after_kind != "message" or not anchor:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, "Invalid history cursor") from None

    rows = repository(conn).search_messages(
        project_id, q, after_created, after_kind, after_resource, limit + 1,
    )
    items = [{
        "project_id": row["project_id"],
        "conversation_id": row["conversation_id"],
        "kind": row["kind"],
        "resource_id": row["resource_id"],
        "run_id": row["run_id"],
        "excerpt": row["content"][:240],
        "created_at": row["created_at"],
    } for row in rows[:limit]]
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = encode_cursor({
            "project": str(project_id),
            "query": digest(q),
            "created": last["created_at"].isoformat(),
            "kind": last["kind"],
            "resource": str(last["resource_id"]),
        })
    return {"items": items, "next_cursor": next_cursor}
