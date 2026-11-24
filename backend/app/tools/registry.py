import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FTimeout
from dataclasses import dataclass
from typing import Callable, Optional, Type

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApprovalRequired, PolicyViolation, ToolError
from app.core.roles import ROLE_RANK
from app.models import Organization
from app.services.audit import audit
from app.services.events import emit_event
from app.services.policy import get_policy


@dataclass
class ToolContext:
    db: Session
    org_id: uuid.UUID
    user_id: Optional[uuid.UUID]
    role: str
    run_id: Optional[uuid.UUID] = None
    approved: bool = False  # True only when an approved, hash-verified Approval backs this call


@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]
    fn: Callable
    min_role: str
    side_effect: bool
    policy_action: Optional[str]
    timeout: Optional[int]


REGISTRY: dict[str, ToolSpec] = {}
_pool = ThreadPoolExecutor(max_workers=8)


def tool(name, input_model, output_model, *, min_role="viewer", side_effect=False, policy_action=None, timeout=None):
    def deco(fn):
        REGISTRY[name] = ToolSpec(name, (fn.__doc__ or "").strip(), input_model, output_model, fn,
                                  min_role, side_effect, policy_action, timeout)
        return fn
    return deco


def _redact(d):
    return {k: (v[:120] + "…" if isinstance(v, str) and len(v) > 120 else v) for k, v in (d or {}).items()}


def call_tool(ctx: ToolContext, name: str, raw: dict) -> dict:
    spec = REGISTRY.get(name)
    if not spec:
        raise ToolError(f"Unknown tool {name}")
    if ROLE_RANK[ctx.role] < ROLE_RANK[spec.min_role]:
        raise PolicyViolation(f"Role '{ctx.role}' may not call {name}")
    if spec.policy_action:  # permission + policy validated at execution time, every time
        org = ctx.db.get(Organization, ctx.org_id)
        pol = get_policy(org.settings, spec.policy_action)
        if pol["mode"] == "restricted":
            raise PolicyViolation(f"{spec.policy_action} is restricted by policy")
        if pol["mode"] == "approval" and not ctx.approved:
            raise ApprovalRequired(f"{name} requires an approved action")
    try:
        args = spec.input_model.model_validate(raw)
    except ValidationError as e:
        raise ToolError(f"Invalid arguments for {name}: {e.errors()[:2]}")

    t0 = time.perf_counter()
    ok, err, out = True, None, None
    try:
        fut = _pool.submit(spec.fn, ctx, args)
        res = fut.result(timeout=spec.timeout or settings.tool_timeout_seconds)
        out = spec.output_model.model_validate(res).model_dump(mode="json")
        return out
    except FTimeout:
        ok, err = False, "timeout"
        raise ToolError(f"{name} timed out")
    except Exception as e:
        ok, err = False, str(e)[:300]
        ctx.db.rollback()
        raise
    finally:
        ms = int((time.perf_counter() - t0) * 1000)
        audit(ctx.db, ctx.org_id, ctx.user_id, f"tool.{name}", "tool", name, ctx.run_id,
              {"ok": ok, "duration_ms": ms, "error": err, "args": _redact(raw)})
        ctx.db.commit()
        if ctx.run_id:
            emit_event(ctx.org_id, ctx.run_id, "tool.called", None, "ok" if ok else "error",
                       {"tool": name, "duration_ms": ms, "error": err, "side_effect": spec.side_effect})
