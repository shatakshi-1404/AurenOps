import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.db import get_db
from app.core.deps import Principal, get_principal, require_role
from app.core.errors import AppError
from app.core.security import encrypt_secret
from app.core.utils import get_scoped, to_dict
from app.models import Integration
from app.schemas import IntegrationIn, RotateIn
from app.services.audit import audit

router = APIRouter(prefix="/integrations", tags=["integrations"])
KINDS = {"crm", "email", "database", "storage"}


@router.get("")
def list_integrations(p: Principal = Depends(get_principal), db=Depends(get_db)):
    rows = db.scalars(select(Integration).where(Integration.org_id == p.org_id))
    return [to_dict(i, exclude=("config_encrypted",)) for i in rows]  # secrets never leave the server


@router.post("")
def create(body: IntegrationIn, p: Principal = Depends(require_role("admin")), db=Depends(get_db)):
    if body.kind not in KINDS:
        raise AppError(400, "bad_kind", f"kind must be one of {sorted(KINDS)}")
    i = Integration(org_id=p.org_id, kind=body.kind, name=body.name, provider=body.provider,
                    config_encrypted=encrypt_secret(json.dumps(body.config)) if body.config else None)
    db.add(i)
    db.flush()
    audit(db, p.org_id, p.user_id, "integration.created", "integration", i.id, details={"kind": body.kind})
    db.commit()
    return to_dict(i, exclude=("config_encrypted",))


@router.post("/{iid}/health")
def health(iid: uuid.UUID, p: Principal = Depends(require_role("operator")), db=Depends(get_db)):
    i = get_scoped(db, Integration, iid, p.org_id)
    i.last_health_at = datetime.now(timezone.utc)
    i.status = "connected"  # mock adapters are always healthy; real adapters ping the provider here
    db.commit()
    return {"id": i.id, "status": i.status, "checked_at": i.last_health_at}


@router.post("/{iid}/rotate")
def rotate(iid: uuid.UUID, body: RotateIn, p: Principal = Depends(require_role("admin")), db=Depends(get_db)):
    i = get_scoped(db, Integration, iid, p.org_id)
    i.config_encrypted = encrypt_secret(json.dumps(body.config))
    i.last_rotated_at = datetime.now(timezone.utc)
    audit(db, p.org_id, p.user_id, "integration.rotated", "integration", i.id)
    db.commit()
    return {"ok": True}


@router.delete("/{iid}")
def delete(iid: uuid.UUID, p: Principal = Depends(require_role("admin")), db=Depends(get_db)):
    i = get_scoped(db, Integration, iid, p.org_id)
    audit(db, p.org_id, p.user_id, "integration.deleted", "integration", i.id)
    db.delete(i)
    db.commit()
    return {"ok": True}
