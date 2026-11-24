import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.db import session_scope
from app.core.redis_client import r
from app.models import AgentRun, WorkflowEvent

log = logging.getLogger(__name__)
TERMINAL = {"COMPLETED", "FAILED", "REJECTED", "CANCELLED"}


def emit_event(org_id, run_id, event, node_id=None, status=None, data=None):
    """Persist (durable history) then publish (live WebSocket)."""
    data = data or {}
    with session_scope() as db:
        ev = WorkflowEvent(org_id=uuid.UUID(str(org_id)), run_id=uuid.UUID(str(run_id)),
                           event=event, node_id=node_id, status=status, data=data)
        db.add(ev)
        db.flush()
        payload = {"id": str(ev.id), "event": event, "run_id": str(run_id), "node_id": node_id,
                   "status": status, "timestamp": ev.created_at.isoformat(), "data": data}
    try:
        r.publish(f"run:{run_id}", json.dumps(payload, default=str))
    except Exception:
        log.warning("redis publish failed")


def set_run_status(org_id, run_id, status, error=None, result=None):
    with session_scope() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.id == uuid.UUID(str(run_id))))
        if not run or run.status == "CANCELLED":
            return
        run.status = status
        now = datetime.now(timezone.utc)
        if status in ("PLANNING", "RUNNING") and not run.started_at:
            run.started_at = now
        if status in TERMINAL:
            run.finished_at = now
        if error is not None:
            run.error = error
        if result is not None:
            run.result = result
    emit_event(org_id, run_id, "run.status", None, status, {"error": error} if error else {})
