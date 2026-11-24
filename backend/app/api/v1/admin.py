import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select

import app.tools.business  # noqa: F401
from app.core.db import get_db
from app.core.deps import Principal, get_principal, require_role
from app.core.errors import AppError
from app.core.roles import ROLE_RANK, ROLES
from app.core.utils import to_dict
from app.models import Membership, Notification, Organization, Tool, User
from app.schemas import PolicyUpdateIn, RoleUpdateIn
from app.services.audit import audit
from app.services.policy import DEFAULT_POLICIES, get_policy

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/members")
def members(p: Principal = Depends(require_role("admin")), db=Depends(get_db)):
    rows = db.execute(select(User.id, User.email, User.full_name, Membership.role)
                      .join(Membership, Membership.user_id == User.id).where(Membership.org_id == p.org_id)).all()
    return [{"user_id": r.id, "email": r.email, "full_name": r.full_name, "role": r.role} for r in rows]


@router.patch("/members/{user_id}")
def set_role(user_id: uuid.UUID, body: RoleUpdateIn, p: Principal = Depends(require_role("admin")), db=Depends(get_db)):
    m = db.scalar(select(Membership).where(Membership.org_id == p.org_id, Membership.user_id == user_id))
    if not m:
        raise AppError(404, "not_found", "Member not found")
    if body.role not in ROLES or ROLE_RANK[body.role] > ROLE_RANK[p.role] or ROLE_RANK[m.role] > ROLE_RANK[p.role]:
        raise AppError(403, "forbidden", "Cannot change to/from a role above yours")
    m.role = body.role
    audit(db, p.org_id, p.user_id, "member.role_changed", "user", user_id, details={"role": body.role})
    db.commit()
    return {"ok": True}


@router.delete("/members/{user_id}")
def remove_member(user_id: uuid.UUID, p: Principal = Depends(require_role("admin")), db=Depends(get_db)):
    m = db.scalar(select(Membership).where(Membership.org_id == p.org_id, Membership.user_id == user_id))
    if not m or ROLE_RANK[m.role] > ROLE_RANK[p.role] or user_id == p.user_id:
        raise AppError(403, "forbidden", "Cannot remove this member")
    db.delete(m)
    audit(db, p.org_id, p.user_id, "member.removed", "user", user_id)
    db.commit()
    return {"ok": True}


@router.get("/policies")
def policies(p: Principal = Depends(require_role("admin")), db=Depends(get_db)):
    org = db.get(Organization, p.org_id)
    return {a: get_policy(org.settings, a) for a in DEFAULT_POLICIES}


@router.put("/policies/{action}")
def set_policy(action: str, body: PolicyUpdateIn, p: Principal = Depends(require_role("admin")), db=Depends(get_db)):
    if action not in DEFAULT_POLICIES or body.mode not in ("auto", "approval", "restricted"):
        raise AppError(400, "bad_policy", "Unknown action or mode")
    org = db.get(Organization, p.org_id)
    s = dict(org.settings or {})
    s.setdefault("policies", {})[action] = body.model_dump(exclude_none=True)
    org.settings = s  # reassign so SQLAlchemy detects the JSONB change
    audit(db, p.org_id, p.user_id, "policy.updated", "policy", action, details=body.model_dump(exclude_none=True))
    db.commit()
    return get_policy(org.settings, action)


@router.get("/tools")
def tools(p: Principal = Depends(get_principal), db=Depends(get_db)):
    return [to_dict(t) for t in db.scalars(select(Tool).where(Tool.org_id == p.org_id).order_by(Tool.name))]


@router.get("/notifications")
def notifications(p: Principal = Depends(get_principal), db=Depends(get_db)):
    rows = db.scalars(select(Notification).where(
        Notification.org_id == p.org_id, (Notification.user_id == p.user_id) | (Notification.user_id.is_(None)))
        .order_by(Notification.created_at.desc()).limit(50))
    return [to_dict(n) for n in rows]


@router.post("/notifications/{nid}/read")
def mark_read(nid: uuid.UUID, p: Principal = Depends(get_principal), db=Depends(get_db)):
    n = db.scalar(select(Notification).where(Notification.id == nid, Notification.org_id == p.org_id))
    if n:
        n.read = True
        db.commit()
    return {"ok": True}


@router.post("/demo-data")
def demo_data(p: Principal = Depends(require_role("admin")), db=Depends(get_db)):
    from app.services.demo_data import seed_demo_data
    res = seed_demo_data(db, p.org_id)
    audit(db, p.org_id, p.user_id, "demo_data.loaded", "organization", p.org_id, details=res)
    db.commit()
    return res
