import json
import logging
import uuid

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import settings
from app.core.db import session_scope
from app.core.errors import RunCancelled
from app.core.logging import setup_logging
from app.core.redis_client import r
from app.models import AgentRun, Document
from app.rag.ingest import ingest_document
from app.services.approvals import expire_stale
from app.services.events import TERMINAL, emit_event, set_run_status
from app.workers.celery_app import celery
from app.workers.queue import enqueue_resume

setup_logging()
log = logging.getLogger(__name__)
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        from app.workflows.graph import build_graph
        pool = ConnectionPool(settings.pg_conninfo, max_size=5, open=True,
                              kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
        saver = PostgresSaver(pool)
        saver.setup()
        _graph = build_graph(saver)
    return _graph


def _drive(run_id: str, graph_input):
    cfg = {"configurable": {"thread_id": run_id}}
    try:
        get_graph().invoke(graph_input, cfg)
    except RunCancelled:
        log.info("run %s cancelled", run_id)
    except Exception as e:
        log.exception("run %s failed", run_id)
        with session_scope() as db:
            run = db.get(AgentRun, uuid.UUID(run_id))
            org_id, status = run.org_id, run.status
        if status not in TERMINAL:
            set_run_status(org_id, run_id, "FAILED", error=str(e)[:500])
            emit_event(org_id, run_id, "run.failed", None, "FAILED", {"error": str(e)[:300]})
        r.lpush("deadletter:runs", json.dumps({"run_id": run_id, "error": str(e)[:500]}))  # dead-letter record


@celery.task(name="run.start", acks_late=True)
def start_run(run_id: str, role: str):
    with session_scope() as db:
        run = db.get(AgentRun, uuid.UUID(run_id))
        state = {"run_id": run_id, "organization_id": str(run.org_id), "user_id": str(run.user_id),
                 "role": role, "request": run.request, "errors": []}
    _drive(run_id, state)


@celery.task(name="run.resume", acks_late=True)
def resume_run(run_id: str, decision: dict):
    _drive(run_id, Command(resume=decision))


@celery.task(name="run.retry", acks_late=True)
def retry_run(run_id: str):
    _drive(run_id, None)  # continues from the last good checkpoint; the failed node re-executes


@celery.task(name="doc.ingest")
def ingest_task(doc_id: str):
    with session_scope() as db:
        doc = db.get(Document, uuid.UUID(doc_id))
        if doc:
            ingest_document(db, doc, bytes(doc.raw or b""))


@celery.task(name="approvals.expire")
def expire_task():
    with session_scope() as db:
        pairs = expire_stale(db)
    for run_id, approval_id in pairs:
        enqueue_resume(run_id, {"decision": "expired", "approval_id": approval_id, "approved_email_ids": []})
