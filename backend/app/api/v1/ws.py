import asyncio
import json
import time
import uuid

from fastapi import APIRouter, WebSocket
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.core.db import session_scope
from app.core.deps import principal_from_token
from app.core.errors import AppError
from app.core.redis_client import async_redis
from app.models import AgentRun, WorkflowEvent

router = APIRouter()


def _auth_and_backlog(token: str, run_id: uuid.UUID):
    with session_scope() as db:
        p = principal_from_token(token, db)
        if not db.scalar(select(AgentRun.id).where(AgentRun.id == run_id, AgentRun.org_id == p.org_id)):
            raise AppError(404, "not_found", "Run not found")
        evs = db.scalars(select(WorkflowEvent).where(WorkflowEvent.run_id == run_id, WorkflowEvent.org_id == p.org_id)
                         .order_by(WorkflowEvent.created_at))
        return [{"id": str(e.id), "event": e.event, "run_id": str(e.run_id), "node_id": e.node_id,
                 "status": e.status, "timestamp": e.created_at.isoformat(), "data": e.data} for e in evs]


@router.websocket("/operations/{run_id}/stream")
async def stream(ws: WebSocket, run_id: uuid.UUID, token: str):
    await ws.accept()
    rd = async_redis()
    ps = rd.pubsub()
    await ps.subscribe(f"run:{run_id}")  # subscribe BEFORE reading backlog so nothing is missed
    try:
        try:
            backlog = await run_in_threadpool(_auth_and_backlog, token, run_id)
        except AppError:
            await ws.close(code=4401)
            return
        seen = set()
        for ev in backlog:
            seen.add(ev["id"])
            await ws.send_json(ev)
        last = time.time()
        while True:
            msg = await ps.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg:
                ev = json.loads(msg["data"])
                if ev["id"] not in seen:
                    seen.add(ev["id"])
                    await ws.send_json(ev)
            elif time.time() - last > 15:
                await ws.send_json({"event": "ping"})
                last = time.time()
            await asyncio.sleep(0)
    except Exception:
        pass  # client disconnected
    finally:
        await ps.close()
        await rd.close()
