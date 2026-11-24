import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.db import get_db
from app.core.deps import Principal, get_principal
from app.core.utils import get_scoped, to_dict
from app.models import Agent, AgentRun

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
def list_agents(p: Principal = Depends(get_principal), db=Depends(get_db)):
    return [to_dict(a) for a in db.scalars(select(Agent).where(Agent.org_id == p.org_id).order_by(Agent.name))]


@router.get("/{agent_id}/runs")
def agent_runs(agent_id: uuid.UUID, p: Principal = Depends(get_principal), db=Depends(get_db)):
    get_scoped(db, Agent, agent_id, p.org_id)
    rows = db.scalars(select(AgentRun).where(AgentRun.agent_id == agent_id, AgentRun.org_id == p.org_id)
                      .order_by(AgentRun.created_at.desc()).limit(100))
    return [to_dict(r) for r in rows]
