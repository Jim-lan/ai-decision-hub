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


def transaction():
    with connect() as conn:
        yield conn


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def audit(conn, action: str, trace: UUID, owner=None, resource=None):
    conn.execute("INSERT INTO audit_events (action, trace_id, owner_id, resource_id) VALUES (%s,%s,%s,%s)",
                 (action, trace, owner, resource))


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
    owner = conn.execute("SELECT owner_id FROM sessions WHERE token_hash=%s AND expires_at > now()",
                         (digest(token),)).fetchone()
    if not owner:
        raise HTTPException(401, "Authentication required")
    return owner["owner_id"]


@router.post("/auth/login", status_code=204)
def login(data: Login, request: Request, response: Response, conn=Depends(transaction)):
    owner = conn.execute("SELECT user_id, password_hash FROM users WHERE login='owner'").fetchone()
    try:
        hasher.verify(owner["password_hash"], data.password)
    except VerifyMismatchError:
        audit(conn, "login_denied", request.state.trace)
        conn.commit()
        raise HTTPException(401, "Invalid credentials") from None
    token = secrets.token_urlsafe(32)
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
    response.delete_cookie(cookie)
