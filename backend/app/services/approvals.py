import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.models import Approval, EmailDraft, Notification


def draft_hash(drafts) -> str:
    """Approval is bound to the exact content of these drafts."""
    items = sorted(
        ({"id": str(d.id), "to": d.to_email, "subject": d.subject, "body": d.body} for d in drafts),
        key=lambda x: x["id"],
    )
    return hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()


def load_drafts(db, org_id, ids):
    if not ids:
        return []
    return list(db.scalars(select(EmailDraft).where(
        EmailDraft.org_id == org_id, EmailDraft.id.in_([uuid.UUID(str(i)) for i in ids]))))


def get_or_create_approval(db, *, org_id, run_id, drafts, items, policy, auto=False):
    existing = db.scalar(select(Approval).where(Approval.run_id == run_id, Approval.action == "send_email"))
    if existing:  # node retries must not duplicate approvals
        return existing
    h = draft_hash(drafts)
    now = datetime.now(timezone.utc)
    a = Approval(
        org_id=org_id, run_id=run_id, action="send_email",
        title=f"Send {len(drafts)} invoice reminders",
        reason="Collection reminders drafted for overdue invoices; sending external email requires approval.",
        agent_key="communication_agent",
        policy=f"send_email:{policy['mode']} (approver >= {policy.get('approver_min_role', 'operator')})",
        risk=policy.get("risk", "medium"),
        status="approved" if auto else "pending",
        payload={"email_ids": [str(d.id) for d in drafts], "items": items,
                 "total_outstanding": round(sum(i["outstanding"] for i in items), 2)},
        payload_hash=h,
        approved_ids=[str(d.id) for d in drafts] if auto else None,
        approved_hash=h if auto else None,
        decision_note="Auto-approved by org policy" if auto else None,
        decided_at=now if auto else None,
        expires_at=now + timedelta(hours=settings.approval_ttl_hours),
    )
    db.add(a)
    db.flush()
    if not auto:
        db.add(Notification(org_id=org_id, user_id=None, title="Approval needed",
                            body=a.title, link=f"/approvals/{a.id}"))
    return a


def expire_stale(db, org_id=None):
    """Mark overdue pending approvals expired; returns [(run_id, approval_id)] to resume as expired."""
    q = select(Approval).where(Approval.status == "pending", Approval.expires_at < datetime.now(timezone.utc))
    if org_id:
        q = q.where(Approval.org_id == org_id)
    out = []
    for a in db.scalars(q.with_for_update(skip_locked=True)):
        a.status = "expired"
        a.decided_at = datetime.now(timezone.utc)
        for d in load_drafts(db, a.org_id, a.payload.get("email_ids", [])):
            if d.status == "draft":
                d.status = "rejected"
        out.append((str(a.run_id), str(a.id)))
    return out
