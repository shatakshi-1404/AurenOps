import json
import logging
import time
import uuid

from sqlalchemy import update

from app.core.config import settings
from app.core.db import session_scope
from app.models import AgentRun
from app.services.events import emit_event

log = logging.getLogger(__name__)
_client = None


def _get():
    global _client
    if not settings.groq_api_key:
        return None
    if _client is None:
        from groq import Groq
        _client = Groq(api_key=settings.groq_api_key, timeout=30)
    return _client


def _call(org_id, run_id, system, user, node, json_mode):
    c = _get()
    if not c:
        return None
    t0 = time.perf_counter()
    try:
        kw = {"response_format": {"type": "json_object"}} if json_mode else {}
        resp = c.chat.completions.create(
            model=settings.groq_model, temperature=0.2,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], **kw)
        text = resp.choices[0].message.content
        u = resp.usage
        total = getattr(u, "total_tokens", 0) or 0
        if run_id:
            with session_scope() as db:
                db.execute(update(AgentRun).where(AgentRun.id == uuid.UUID(str(run_id)))
                           .values(token_usage=AgentRun.token_usage + total))
            emit_event(org_id, run_id, "llm.call", node, "ok", {
                "model": settings.groq_model, "prompt_tokens": getattr(u, "prompt_tokens", 0),
                "completion_tokens": getattr(u, "completion_tokens", 0), "total_tokens": total,
                "latency_ms": int((time.perf_counter() - t0) * 1000)})
        return text
    except Exception as e:  # LLM failure must never break the workflow: callers have fallbacks
        log.warning("llm call failed: %s", e)
        if run_id:
            emit_event(org_id, run_id, "llm.call", node, "error", {"error": str(e)[:200]})
        return None


def llm_json(org_id, run_id, system, user, node=None):
    text = _call(org_id, run_id, system, user, node, True)
    try:
        return json.loads(text) if text else None
    except json.JSONDecodeError:
        return None


def llm_text(org_id, run_id, system, user, node=None):
    return _call(org_id, run_id, system, user, node, False)
