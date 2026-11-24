from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import Integer, cast, func, select

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import Principal, get_principal
from app.core.utils import to_dict
from app.models import Agent, AgentRun, Approval, EmailDraft, WorkflowEvent, WorkflowNode

router = APIRouter(tags=["dashboard"])
RUNNING = ("PLANNING", "RUNNING", "APPROVED", "EXECUTING", "VERIFYING", "RETRYING")


@router.get("/dashboard")
def dashboard(p: Principal = Depends(get_principal), db=Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=30)
    org = AgentRun.org_id == p.org_id
    completed = db.scalar(select(func.count()).where(org, AgentRun.status == "COMPLETED", AgentRun.created_at >= since))
    failed = db.scalar(select(func.count()).where(org, AgentRun.status == "FAILED", AgentRun.created_at >= since))
    sent = db.scalar(select(func.count()).where(EmailDraft.org_id == p.org_id, EmailDraft.status == "sent",
                                                EmailDraft.created_at >= since))
    turnaround = db.scalar(select(func.avg(func.extract("epoch", Approval.decided_at - Approval.created_at)))
                           .where(Approval.org_id == p.org_id, Approval.status == "approved",
                                  Approval.decided_by.is_not(None)))
    avg_dur = db.scalar(select(func.avg(func.extract("epoch", AgentRun.finished_at - AgentRun.started_at)))
                        .where(org, AgentRun.status == "COMPLETED"))
    per_agent = db.execute(
        select(WorkflowNode.agent_key, func.count(), func.avg(WorkflowNode.duration_ms),
               func.count().filter(WorkflowNode.status == "failed"))
        .where(WorkflowNode.org_id == p.org_id).group_by(WorkflowNode.agent_key)).all()
    daily = db.execute(
        select(func.date_trunc("day", AgentRun.created_at).label("d"), func.count())
        .where(org, AgentRun.created_at >= since).group_by("d").order_by("d")).all()
    return {
        "active_agents": db.scalar(select(func.count()).where(Agent.org_id == p.org_id, Agent.enabled)),
        "runs_in_flight": db.scalar(select(func.count()).where(org, AgentRun.status.in_(RUNNING))),
        "pending_approvals": db.scalar(select(func.count()).where(Approval.org_id == p.org_id, Approval.status == "pending")),
        "tasks_completed_30d": completed,
        "success_rate": round(completed / (completed + failed) * 100, 1) if (completed + failed) else None,
        "approval_turnaround_seconds": round(turnaround, 1) if turnaround else None,
        "avg_execution_seconds": round(avg_dur, 1) if avg_dur else None,
        "emails_sent_30d": sent,
        "estimated_minutes_saved": sent * settings.minutes_saved_per_email,  # estimate, not a measurement
        "agent_performance": [{"agent": a, "executions": c, "avg_ms": round(ms or 0), "failures": f} for a, c, ms, f in per_agent],
        "runs_per_day": [{"day": d.date().isoformat(), "runs": c} for d, c in daily],
        "recent_runs": [to_dict(r) for r in db.scalars(select(AgentRun).where(org).order_by(AgentRun.created_at.desc()).limit(8))],
    }


@router.get("/observability/events")
def obs_events(run_id: str | None = None, event: str | None = None, node: str | None = None,
               status: str | None = None, since: datetime | None = None, limit: int = 200,
               p: Principal = Depends(get_principal), db=Depends(get_db)):
    q = select(WorkflowEvent).where(WorkflowEvent.org_id == p.org_id)
    for col, val in ((WorkflowEvent.run_id, run_id), (WorkflowEvent.event, event),
                     (WorkflowEvent.node_id, node), (WorkflowEvent.status, status)):
        if val:
            q = q.where(col == val)
    if since:
        q = q.where(WorkflowEvent.created_at >= since)
    return [to_dict(e) for e in db.scalars(q.order_by(WorkflowEvent.created_at.desc()).limit(min(limit, 1000)))]


@router.get("/observability/tool-calls")
def tool_calls(limit: int = 200, p: Principal = Depends(get_principal), db=Depends(get_db)):
    rows = db.scalars(select(WorkflowEvent).where(WorkflowEvent.org_id == p.org_id, WorkflowEvent.event == "tool.called")
                      .order_by(WorkflowEvent.created_at.desc()).limit(min(limit, 1000)))
    return [to_dict(e) for e in rows]


@router.get("/observability/llm-usage")
def llm_usage(p: Principal = Depends(get_principal), db=Depends(get_db)):
    tok = cast(WorkflowEvent.data["total_tokens"].astext, Integer)
    lat = cast(WorkflowEvent.data["latency_ms"].astext, Integer)
    rows = db.execute(select(WorkflowEvent.data["model"].astext, func.count(), func.sum(tok), func.avg(lat))
                      .where(WorkflowEvent.org_id == p.org_id, WorkflowEvent.event == "llm.call",
                             WorkflowEvent.status == "ok").group_by(WorkflowEvent.data["model"].astext)).all()
    return [{"model": m, "calls": c, "total_tokens": int(t or 0), "avg_latency_ms": round(l or 0)} for m, c, t, l in rows]
