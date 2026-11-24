import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select

from app.core.db import get_db
from app.core.deps import Principal, get_principal, require_role
from app.core.errors import AppError
from app.core.roles import ROLES
from app.core.utils import get_scoped, to_dict
from app.models import Document, DocumentChunk
from app.rag.search import hybrid_search
from app.schemas import SearchIn
from app.services.audit import audit
from app.workers.queue import enqueue_ingest

router = APIRouter(tags=["knowledge"])
MAX_BYTES = 15 * 1024 * 1024


@router.post("/documents")
async def upload(file: UploadFile = File(...), category: str = Form("general"), access_roles: str = Form(""),
                 p: Principal = Depends(require_role("operator")), db=Depends(get_db)):
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise AppError(413, "too_large", "Max 15MB")
    if not (file.filename or "").lower().endswith((".pdf", ".docx", ".txt", ".md")):
        raise AppError(400, "bad_type", "Use PDF, DOCX, TXT or MD")
    roles = [x.strip() for x in access_roles.split(",") if x.strip() in ROLES] or None
    doc = Document(org_id=p.org_id, filename=file.filename, content_type=file.content_type or "", category=category,
                   access_roles=roles, uploaded_by=p.user_id, raw=data, status="processing")
    db.add(doc)
    db.flush()
    audit(db, p.org_id, p.user_id, "document.uploaded", "document", doc.id, details={"filename": file.filename})
    db.commit()
    enqueue_ingest(str(doc.id))
    return to_dict(doc, exclude=("raw",))


@router.get("/documents")
def list_documents(p: Principal = Depends(get_principal), db=Depends(get_db)):
    docs = db.scalars(select(Document).where(Document.org_id == p.org_id).order_by(Document.created_at.desc()))
    return [to_dict(d, exclude=("raw",)) for d in docs
            if d.access_roles is None or p.role in d.access_roles or p.role in ("admin", "owner")]


@router.get("/documents/{doc_id}/chunks")
def chunks(doc_id: uuid.UUID, p: Principal = Depends(get_principal), db=Depends(get_db)):
    d = get_scoped(db, Document, doc_id, p.org_id)
    if d.access_roles is not None and p.role not in d.access_roles and p.role not in ("admin", "owner"):
        raise AppError(403, "forbidden", "No access to this document")
    rows = db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == d.id, DocumentChunk.org_id == p.org_id)
                      .order_by(DocumentChunk.idx))
    return [{"id": c.id, "idx": c.idx, "content": c.content, "metadata": c.meta} for c in rows]


@router.post("/documents/{doc_id}/reindex")
def reindex(doc_id: uuid.UUID, p: Principal = Depends(require_role("operator")), db=Depends(get_db)):
    d = get_scoped(db, Document, doc_id, p.org_id)
    d.status = "processing"
    db.commit()
    enqueue_ingest(str(d.id))
    return {"ok": True}


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: uuid.UUID, p: Principal = Depends(require_role("admin")), db=Depends(get_db)):
    d = get_scoped(db, Document, doc_id, p.org_id)
    audit(db, p.org_id, p.user_id, "document.deleted", "document", d.id, details={"filename": d.filename})
    db.delete(d)
    db.commit()
    return {"ok": True}


@router.post("/knowledge/search")
def search(body: SearchIn, p: Principal = Depends(get_principal), db=Depends(get_db)):
    return {"results": hybrid_search(db, p.org_id, p.role, body.query, body.k, body.category)}
