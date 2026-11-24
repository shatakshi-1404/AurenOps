import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api
from app.core.config import settings
from app.core.db import engine
from app.core.errors import AppError
from app.core.logging import request_id_ctx, setup_logging
from app.core.redis_client import r

setup_logging()
log = logging.getLogger("aurenops")
app = FastAPI(title="AurenOps API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def request_id_mw(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request_id_ctx.set(rid)
    resp = await call_next(request)
    resp.headers["x-request-id"] = rid
    return resp


@app.exception_handler(AppError)
async def app_error(_, e: AppError):
    return JSONResponse(status_code=e.status, content={"error": {"code": e.code, "message": e.message}})


@app.exception_handler(Exception)
async def unhandled(_, e: Exception):
    log.exception("unhandled error")
    return JSONResponse(status_code=500, content={"error": {"code": "internal", "message": "Internal server error"}})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    r.ping()
    return {"status": "ready"}


app.include_router(api)
