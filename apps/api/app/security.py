import hashlib
import os
import secrets
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.contracts import Login
from app.db import connect, read_secret

router = APIRouter(prefix="/v1")
hasher = PasswordHasher()
cookie = "hub_session"
failed_attempt_limit = 5
audit_actions = {
    "login", "login_denied", "logout", "project_created", "conversation_created",
    "message_appended", "run_created", "run_transition", "target_transition",
    "context_allowed", "context_denied", "dispatch_attempt", "manual_original_imported",
    "budget_reserved", "budget_denied", "usage_reconciled", "report_published",
    "decision_saved", "provider_config_changed", "project_purged", "project_exported",
    "project_imported",
}
audit_outcomes = {"accepted", "denied", "failed", "partial", "cancelled", "unknown"}


def transaction():
    with connect() as conn:
        yield conn


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def audit(conn, action: str, trace: UUID, owner=None, resource=None, *, project=None,
          outcome="accepted"):
    if action not in audit_actions or outcome not in audit_outcomes:
        raise ValueError("Unsupported audit classification")
    conn.execute("""INSERT INTO audit_events
        (action, trace_id, owner_id, project_id, resource_id, outcome)
        VALUES (%s,%s,%s,%s,%s,%s)""",
        (action, trace, owner, project, resource, outcome))


def bootstrap():
    with connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(1740092)")
        if not conn.execute("SELECT 1 FROM users WHERE login='owner'").fetchone():
            password = read_secret("OWNER_PASSWORD")
            if len(password) < 12:
                raise ValueError("Use at least twelve characters for the owner password")
            conn.execute("INSERT INTO users (login, password_hash) VALUES ('owner', %s)", (hasher.hash(password),))


def principal(request: Request, conn=Depends(transaction)) -> UUID:
    token = request.cookies.get(cookie, "")
    token_hash = digest(token)
    session = conn.execute("""SELECT owner_id, expires_at > now() AS active
        FROM sessions WHERE token_hash=%s""", (token_hash,)).fetchone()
    if not session or not session["active"]:
        if session:
            conn.execute("DELETE FROM sessions WHERE token_hash=%s", (token_hash,))
            conn.commit()
        raise HTTPException(401, "Authentication required")
    return session["owner_id"]


def record_failed_login(conn):
    row = conn.execute("""INSERT INTO login_throttle
            (login, failed_attempts, window_started, blocked_until)
        VALUES ('owner', 1, now(), NULL)
        ON CONFLICT (login) DO UPDATE SET
            failed_attempts = CASE
                WHEN login_throttle.window_started <= now() - interval '15 minutes' THEN 1
                ELSE login_throttle.failed_attempts + 1
            END,
            window_started = CASE
                WHEN login_throttle.window_started <= now() - interval '15 minutes' THEN now()
                ELSE login_throttle.window_started
            END,
            blocked_until = CASE
                WHEN (CASE
                    WHEN login_throttle.window_started <= now() - interval '15 minutes' THEN 1
                    ELSE login_throttle.failed_attempts + 1
                END) >= %s THEN now() + interval '15 minutes'
                ELSE NULL
            END
        RETURNING blocked_until > now() AS blocked""", (failed_attempt_limit,)).fetchone()
    return row["blocked"]


@router.post("/auth/login", status_code=204)
def login(data: Login, request: Request, response: Response, conn=Depends(transaction)):
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('login:owner', 0))")
    owner = conn.execute("SELECT user_id, password_hash FROM users WHERE login='owner'").fetchone()
    blocked = conn.execute("""SELECT blocked_until > now() AS blocked
        FROM login_throttle WHERE login='owner'""").fetchone()
    if blocked and blocked["blocked"]:
        audit(conn, "login_denied", request.state.trace, owner["user_id"], outcome="denied")
        conn.commit()
        raise HTTPException(429, "Login temporarily unavailable")
    try:
        hasher.verify(owner["password_hash"], data.password)
    except VerifyMismatchError:
        now_blocked = record_failed_login(conn)
        audit(conn, "login_denied", request.state.trace, owner["user_id"], outcome="denied")
        conn.commit()
        if now_blocked:
            raise HTTPException(429, "Login temporarily unavailable") from None
        raise HTTPException(401, "Invalid credentials") from None
    token = secrets.token_urlsafe(32)
    conn.execute("DELETE FROM login_throttle WHERE login='owner'")
    conn.execute("DELETE FROM sessions WHERE expires_at <= now() OR token_hash=%s",
                 (digest(request.cookies.get(cookie, "")),))
    conn.execute("INSERT INTO sessions VALUES (%s,%s,now() + interval '12 hours')",
                 (digest(token), owner["user_id"]))
    audit(conn, "login", request.state.trace, owner["user_id"])
    response.set_cookie(cookie, token, httponly=True, samesite="strict", max_age=43200,
                        secure=os.environ["PUBLIC_BASE_URL"].startswith("https://"))


@router.get("/auth/session")
def session(owner=Depends(principal)):
    return {"owner_id": owner}


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, owner=Depends(principal), conn=Depends(transaction)):
    conn.execute("DELETE FROM sessions WHERE token_hash=%s", (digest(request.cookies[cookie]),))
    audit(conn, "logout", request.state.trace, owner)
    response.delete_cookie(cookie, httponly=True, samesite="strict",
                           secure=os.environ["PUBLIC_BASE_URL"].startswith("https://"))
