import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select

from app.core.db import get_db
from app.core.deps import Principal, get_principal, require_role
from app.core.utils import get_scoped, to_dict
from app.models import Report
from app.schemas import ReportIn
from app.services.audit import audit
from app.services.reports import create_report, report_pdf_bytes

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("")
def generate(body: ReportIn, p: Principal = Depends(require_role("operator")), db=Depends(get_db)):
    rep = create_report(db, p.org_id, None, body.kind)
    audit(db, p.org_id, p.user_id, "report.generated", "report", rep.id)
    db.commit()
    return to_dict(rep, exclude=("csv",))


@router.get("")
def list_reports(p: Principal = Depends(get_principal), db=Depends(get_db)):
    rows = db.scalars(select(Report).where(Report.org_id == p.org_id).order_by(Report.created_at.desc()).limit(100))
    return [to_dict(r, exclude=("csv",)) for r in rows]


@router.get("/{rid}")
def get_report(rid: uuid.UUID, p: Principal = Depends(get_principal), db=Depends(get_db)):
    return to_dict(get_scoped(db, Report, rid, p.org_id), exclude=("csv",))


@router.get("/{rid}/csv")
def csv_export(rid: uuid.UUID, p: Principal = Depends(get_principal), db=Depends(get_db)):
    rep = get_scoped(db, Report, rid, p.org_id)
    return Response(rep.csv, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="report-{rid}.csv"'})


@router.get("/{rid}/pdf")
def pdf_export(rid: uuid.UUID, p: Principal = Depends(get_principal), db=Depends(get_db)):
    rep = get_scoped(db, Report, rid, p.org_id)
    return Response(report_pdf_bytes(rep), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="report-{rid}.pdf"'})
