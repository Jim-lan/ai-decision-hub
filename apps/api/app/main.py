from contextlib import asynccontextmanager
import os
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app import runs, security, workspace
from app.db import connect


@asynccontextmanager
async def lifespan(app):
    security.bootstrap()
    yield


app = FastAPI(title="Personal AI Decision Hub", version="0.1.0", lifespan=lifespan)
app.include_router(security.router)
app.include_router(workspace.router)
app.include_router(runs.router)


def problem(request, status, detail):
    code = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found",
            409: "conflict", 422: "invalid_input"}.get(status, "request_error")
    return JSONResponse({"type": "about:blank", "title": detail, "status": status,
                         "error_code": code, "trace_id": str(request.state.trace)},
                        status_code=status, media_type="application/problem+json")


@app.middleware("http")
async def protect(request: Request, call_next):
    request.state.trace = uuid4()
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("origin") != os.environ["PUBLIC_BASE_URL"]:
        response = problem(request, 403, "Request origin is not allowed")
    else:
        response = await call_next(request)
    response.headers["X-Trace-ID"] = str(request.state.trace)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def http_error(request, error):
    return problem(request, error.status_code, error.detail)


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    return problem(request, 422, "Request validation failed")


@app.get("/v1/health")
def health():
    with connect() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}
