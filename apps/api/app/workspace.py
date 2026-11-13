import base64
import binascii
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.contracts import Conversation, History, Message, Named, NewConversation, NewMessage, Project
from app.security import audit, digest, principal, transaction

router = APIRouter(prefix="/v1")


def require_project(conn, project_id, owner):
    row = conn.execute("SELECT * FROM projects WHERE project_id=%s AND owner_id=%s",
                       (project_id, owner)).fetchone()
    if not row:
        raise HTTPException(404, "Project not found")
    return row


def conversation(conn, conversation_id, owner, *, lock=False):
    query = """SELECT c.* FROM conversations c JOIN projects p USING (project_id)
               WHERE c.conversation_id=%s AND p.owner_id=%s"""
    if lock:
        query += " FOR UPDATE OF c"
    row = conn.execute(query, (conversation_id, owner)).fetchone()
    if not row:
        raise HTTPException(404, "Conversation not found")
    return row


def insert_message(conn, conversation_id, content):
    # The caller holds the conversation row lock until commit.
    return conn.execute("""
        INSERT INTO messages (conversation_id, sequence, role, content, source_hash)
        SELECT %s, COALESCE(MAX(sequence),0)+1, 'user', %s, %s FROM messages WHERE conversation_id=%s
        RETURNING *""", (conversation_id, content, digest(content), conversation_id)).fetchone()


@router.post("/projects", response_model=Project, status_code=201)
def create_project(data: Named, request: Request, owner=Depends(principal), conn=Depends(transaction)):
    row = conn.execute("INSERT INTO projects (name, owner_id) VALUES (%s,%s) RETURNING *",
                       (data.name, owner)).fetchone()
    audit(conn, "project_created", request.state.trace, owner, row["project_id"],
          project=row["project_id"])
    return row


@router.get("/projects", response_model=list[Project])
def projects(owner=Depends(principal), conn=Depends(transaction)):
    return conn.execute("SELECT * FROM projects WHERE owner_id=%s ORDER BY created_at, project_id",
                        (owner,)).fetchall()


@router.get("/projects/{project_id}", response_model=Project)
def project(project_id: UUID, owner=Depends(principal), conn=Depends(transaction)):
    return require_project(conn, project_id, owner)


@router.post("/conversations", response_model=Conversation, status_code=201)
def create_conversation(data: NewConversation, request: Request, owner=Depends(principal), conn=Depends(transaction)):
    require_project(conn, data.project_id, owner)
    row = conn.execute("INSERT INTO conversations (project_id, title) VALUES (%s,%s) RETURNING *",
                       (data.project_id, data.title.strip())).fetchone()
    audit(conn, "conversation_created", request.state.trace, owner, row["conversation_id"],
          project=data.project_id)
    return row


@router.get("/projects/{project_id}/conversations", response_model=list[Conversation])
def conversations(project_id: UUID, owner=Depends(principal), conn=Depends(transaction)):
    require_project(conn, project_id, owner)
    return conn.execute("SELECT * FROM conversations WHERE project_id=%s ORDER BY created_at, conversation_id",
                        (project_id,)).fetchall()


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
    rows = conn.execute("""
        SELECT * FROM messages WHERE conversation_id=%s AND sequence>%s ORDER BY sequence LIMIT %s
    """, (conversation_id, sequence, limit + 1)).fetchall()
    cursor_out = None
    if len(rows) > limit:
        key = f"{conversation_id}:{rows[limit-1]['sequence']}"
        cursor_out = base64.urlsafe_b64encode(key.encode()).decode()
    return {"items": rows[:limit], "next_cursor": cursor_out}
