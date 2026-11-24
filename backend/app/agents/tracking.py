import functools
import json
import time
import uuid
from datetime import datetime, timezone

from langgraph.errors import GraphBubbleUp
from sqlalchemy import select

from app.core.db import session_scope
from app.core.errors import ApprovalRequired, PolicyViolation, RunCancelled
from app.models import AgentRun, WorkflowNode
from app.services.events import emit_event, set_run_status


def _json(x, limit=200_000):
    s = json.dumps(x, default=str)
    return json.loads(s) if len(s) <= limit else {"truncated": True, "size": len(s)}


def ensure_active(run_id):
    with session_scope() as db:
        run = db.get(AgentRun, uuid.UUID(run_id))
        if not run or run.status == "CANCELLED":
            raise RunCancelled(run_id)


def _node(run_id, org_id, key, agent, status, **kw):
    with session_scope() as db:
        n = db.scalar(select(WorkflowNode).where(WorkflowNode.run_id == uuid.UUID(run_id), WorkflowNode.node_key == key))
        if not n:
            n = WorkflowNode(run_id=uuid.UUID(run_id), org_id=uuid.UUID(org_id), node_key=key, agent_key=agent)
            db.add(n)
        n.status = status
        for k, v in kw.items():
            setattr(n, k, v)


def tracked(node_key, agent_key, status="RUNNING", max_attempts=3, input_keys=()):
    """Wrap a graph node: status, events, timing, bounded exponential-backoff retries."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(state):
            run_id, org = state["run_id"], state["organization_id"]
            ensure_active(run_id)
            if status:
                set_run_status(org, run_id, status)
            for attempt in range(1, max_attempts + 1):
                t0 = time.perf_counter()
                _node(run_id, org, node_key, agent_key, "running", attempts=attempt,
                      started_at=datetime.now(timezone.utc),
                      input=_json({k: state.get(k) for k in input_keys}))
                emit_event(org, run_id, "node.started", node_key, "running", {"attempt": attempt, "agent": agent_key})
                try:
                    out = fn(state) or {}
                except GraphBubbleUp:  # interrupt() for human approval
                    _node(run_id, org, node_key, agent_key, "waiting_approval")
                    emit_event(org, run_id, "node.waiting", node_key, "waiting_approval", {"agent": agent_key})
                    raise
                except RunCancelled:
                    raise
                except (PolicyViolation, ApprovalRequired) as e:  # never retried
                    _node(run_id, org, node_key, agent_key, "failed", error=str(e),
                          finished_at=datetime.now(timezone.utc))
                    emit_event(org, run_id, "node.failed", node_key, "failed", {"error": str(e), "agent": agent_key})
                    raise
                except Exception as e:
                    if attempt < max_attempts:
                        emit_event(org, run_id, "node.retrying", node_key, "retrying",
                                   {"attempt": attempt, "error": str(e)[:300], "agent": agent_key})
                        time.sleep(0.5 * 2 ** attempt)
                        continue
                    _node(run_id, org, node_key, agent_key, "failed", error=str(e)[:1000],
                          finished_at=datetime.now(timezone.utc), duration_ms=int((time.perf_counter() - t0) * 1000))
                    emit_event(org, run_id, "node.failed", node_key, "failed",
                               {"error": str(e)[:300], "attempts": attempt, "agent": agent_key})
                    raise
                ms = int((time.perf_counter() - t0) * 1000)
                _node(run_id, org, node_key, agent_key, "completed", output=_json(out),
                      finished_at=datetime.now(timezone.utc), duration_ms=ms, error=None)
                emit_event(org, run_id, "node.completed", node_key, "completed", {"duration_ms": ms, "agent": agent_key})
                return out
        return wrapper
    return deco
