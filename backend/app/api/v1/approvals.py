import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.db import get_db
from app.core.deps import Principal, get_principal, require_role
from app.core.errors import AppError
from app.core.utils import get_scoped, to_dict
from app.models import Approval, EmailDraft, Organization
from app.schemas import ApproveIn, EditApprovalIn, RejectIn
from app.services.approvals import draft_hash, expire_stale, load_drafts
from app.services.audit import audit
from app.services.events import emit_event
from app.services.policy import approver_allowed, get_policy
from app.workers.queue import enqueue_resume

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _expire_and_resume(db, org_id):
    pairs = expire_stale(db, org_id)
    if pairs:
        db.commit()
        for run_id, aid in pairs:
            enqueue_resume(run_id, {"decision": "expired", "approval_id": aid, "approved_email_ids": []})


def _detail(db, a: Approval):
    drafts = load_drafts(db, a.org_id, a.payload.get("email_ids", []))
    return {**to_dict(a), "current_payload_hash": draft_hash(drafts),
            "drafts": [{**to_dict(d, exclude=("idempotency_key",))} for d in drafts]}


@router.get("")
def list_approvals(status: str | None = None, p: Principal = Depends(get_principal), db=Depends(get_db)):
    _expire_and_resume(db, p.org_id)
    q = select(Approval).where(Approval.org_id == p.org_id)
    if status:
        q = q.where(Approval.status == status)
    return [to_dict(a) for a in db.scalars(q.order_by(Approval.created_at.desc()).limit(200))]


@router.get("/{approval_id}")
def get_approval(approval_id: uuid.UUID, p: Principal = Depends(get_principal), db=Depends(get_db)):
    return _detail(db, get_scoped(db, Approval, approval_id, p.org_id))


@router.patch("/{approval_id}")
def edit_approval(approval_id: uuid.UUID, body: EditApprovalIn, p: Principal = Depends(require_role("operator")),
                  db=Depends(get_db)):
    """Edit proposed drafts. Changes the payload hash, so any earlier review of the old content is stale."""
    a = get_scoped(db, Approval, approval_id, p.org_id)
    if a.status != "pending":
        raise AppError(409, "not_editable", f"Approval is {a.status}")
    allowed = set(a.payload["email_ids"])
    for e in body.drafts:
        if str(e.email_id) not in allowed:
            raise AppError(400, "bad_draft", "Draft not part of this approval")
        d = get_scoped(db, EmailDraft, e.email_id, p.org_id)
        if e.subject is not None:
            d.subject = e.subject
        if e.body is not None:
            d.body = e.body
        d.edited = True
    db.flush()
    a.payload_hash = draft_hash(load_drafts(db, p.org_id, a.payload["email_ids"]))
    audit(db, p.org_id, p.user_id, "approval.edited", "approval", a.id, a.run_id, {"edited": len(body.drafts)})
    db.commit()
    return _detail(db, a)


@router.post("/{approval_id}/approve")
def approve(approval_id: uuid.UUID, body: ApproveIn, p: Principal = Depends(require_role("operator")),
            db=Depends(get_db)):
    a = db.scalar(select(Approval).where(Approval.id == approval_id, Approval.org_id == p.org_id).with_for_update())
    if not a:
        raise AppError(404, "not_found", "Approval not found")
    if a.status != "pending":
        raise AppError(409, "already_decided", f"Approval is {a.status}")
    if a.expires_at and a.expires_at < datetime.now(timezone.utc):
        _expire_and_resume(db, p.org_id)
        raise AppError(410, "expired", "Approval expired")
    pol = get_policy(db.get(Organization, p.org_id).settings, "send_email")
    if not approver_allowed(pol, p.role):
        raise AppError(403, "forbidden", f"Policy requires {pol.get('approver_min_role')} to approve")
    all_drafts = load_drafts(db, p.org_id, a.payload["email_ids"])
    if draft_hash(all_drafts) != body.payload_hash or a.payload_hash != body.payload_hash:
        raise AppError(409, "stale_approval", "The proposed action changed since you reviewed it. Reload and re-review.")
    chosen = {str(i) for i in body.email_ids} if body.email_ids is not None else {str(d.id) for d in all_drafts}
    if not chosen or not chosen <= {str(d.id) for d in all_drafts}:
        raise AppError(400, "bad_selection", "Invalid selection")
    selected = [d for d in all_drafts if str(d.id) in chosen]
    for d in all_drafts:
        d.status = "approved" if str(d.id) in chosen else "rejected"
    a.status, a.approved_ids, a.approved_hash = "approved", sorted(chosen), draft_hash(selected)
    a.decided_by, a.decided_at, a.decision_note = p.user_id, datetime.now(timezone.utc), body.note
    audit(db, p.org_id, p.user_id, "approval.approved", "approval", a.id, a.run_id,
          {"approved": len(chosen), "of": len(all_drafts), "hash": a.approved_hash})
    db.commit()
    emit_event(p.org_id, a.run_id, "approval.decided", "approval_gate", "approved", {"approval_id": str(a.id)})
    enqueue_resume(str(a.run_id), {"decision": "approved", "approval_id": str(a.id),
                                   "approved_email_ids": sorted(chosen), "decided_by": str(p.user_id)})
    return {"ok": True, "approved": len(chosen)}


@router.post("/{approval_id}/reject")
def reject(approval_id: uuid.UUID, body: RejectIn, p: Principal = Depends(require_role("operator")),
           db=Depends(get_db)):
    a = db.scalar(select(Approval).where(Approval.id == approval_id, Approval.org_id == p.org_id).with_for_update())
    if not a:
        raise AppError(404, "not_found", "Approval not found")
    if a.status != "pending":
        raise AppError(409, "already_decided", f"Approval is {a.status}")
    a.status, a.decided_by, a.decided_at, a.decision_note = "rejected", p.user_id, datetime.now(timezone.utc), body.note
    for d in load_drafts(db, p.org_id, a.payload["email_ids"]):
        d.status = "rejected"
    audit(db, p.org_id, p.user_id, "approval.rejected", "approval", a.id, a.run_id, {"note": body.note})
    db.commit()
    emit_event(p.org_id, a.run_id, "approval.decided", "approval_gate", "rejected", {"approval_id": str(a.id)})
    enqueue_resume(str(a.run_id), {"decision": "rejected", "approval_id": str(a.id), "approved_email_ids": []})
    return {"ok": True}
