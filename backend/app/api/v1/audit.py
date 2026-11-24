from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.db import get_db
from app.core.deps import Principal, require_role
from app.core.utils import to_dict
from app.models import AuditLog

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("")
def list_audit(action: str | None = None, run_id: str | None = None, since: datetime | None = None,
               limit: int = 100, offset: int = 0, p: Principal = Depends(require_role("admin")), db=Depends(get_db)):
    q = select(AuditLog).where(AuditLog.org_id == p.org_id)
    if action:
        q = q.where(AuditLog.action.like(f"{action}%"))
    if run_id:
        q = q.where(AuditLog.run_id == run_id)
    if since:
        q = q.where(AuditLog.created_at >= since)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(AuditLog.created_at.desc()).limit(min(limit, 500)).offset(offset))
    return {"total": total, "items": [to_dict(a) for a in rows]}
