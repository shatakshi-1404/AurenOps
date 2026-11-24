import csv
import io
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select

from app.models import Customer, EmailDraft, Invoice, Report


def build_collection_summary(db, org_id, run_id=None) -> dict:
    today = date.today()
    rows = db.execute(
        select(Invoice, Customer).join(Customer, Customer.id == Invoice.customer_id)
        .where(Invoice.org_id == org_id, Invoice.status.in_(["open", "overdue"]), Invoice.due_date < today)
    ).all()
    buckets = {"1-30": [0, 0.0], "31-60": [0, 0.0], "61-90": [0, 0.0], "90+": [0, 0.0]}
    by_cust: dict = {}
    total = 0.0
    for inv, c in rows:
        out = float(inv.amount - inv.amount_paid)
        if out <= 0:
            continue
        days = (today - inv.due_date).days
        b = "1-30" if days <= 30 else "31-60" if days <= 60 else "61-90" if days <= 90 else "90+"
        buckets[b][0] += 1
        buckets[b][1] += out
        total += out
        e = by_cust.setdefault(str(c.id), {"customer": c.name, "email": c.email, "invoices": 0,
                                           "outstanding": 0.0, "max_days_overdue": 0})
        e["invoices"] += 1
        e["outstanding"] = round(e["outstanding"] + out, 2)
        e["max_days_overdue"] = max(e["max_days_overdue"], days)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overdue_invoice_count": sum(v[0] for v in buckets.values()),
        "total_outstanding": round(total, 2),
        "aging": {k: {"count": v[0], "amount": round(v[1], 2)} for k, v in buckets.items()},
        "top_customers": sorted(by_cust.values(), key=lambda x: -x["outstanding"])[:20],
    }
    if run_id:
        counts = dict(db.execute(select(EmailDraft.status, func.count()).where(
            EmailDraft.org_id == org_id, EmailDraft.run_id == run_id).group_by(EmailDraft.status)).all())
        failures = [{"to": d.to_email, "error": d.error} for d in db.scalars(select(EmailDraft).where(
            EmailDraft.org_id == org_id, EmailDraft.run_id == run_id, EmailDraft.status == "failed"))]
        summary["run_actions"] = {"email_status_counts": counts, "failures": failures}
    return summary


def summary_to_csv(summary: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["customer", "email", "overdue_invoices", "outstanding", "max_days_overdue"])
    for c in summary.get("top_customers", []):
        w.writerow([c["customer"], c["email"], c["invoices"], c["outstanding"], c["max_days_overdue"]])
    return buf.getvalue()


def create_report(db, org_id, run_id=None, kind="collection") -> Report:
    s = build_collection_summary(db, org_id, run_id)
    rep = Report(org_id=org_id, run_id=run_id, kind=kind, summary=s, csv=summary_to_csv(s))
    db.add(rep)
    db.flush()
    return rep


def report_pdf_bytes(rep: Report) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    s = rep.summary

    def line(t, size=10, dy=16):
        nonlocal y
        if y < 60:
            c.showPage()
            y = 800
        c.setFont("Helvetica", size)
        c.drawString(50, y, t)
        y -= dy

    line("AurenOps - Collection Report", 16, 26)
    line(f"Generated: {s['generated_at']}")
    line(f"Overdue invoices: {s['overdue_invoice_count']}   Total outstanding: INR {s['total_outstanding']:,.2f}", 11, 24)
    line("Aging", 12)
    for k, v in s["aging"].items():
        line(f"  {k} days: {v['count']} invoices, INR {v['amount']:,.2f}")
    line("")
    line("Top customers by outstanding", 12)
    for cst in s["top_customers"]:
        line(f"  {cst['customer'][:34]:34}  INR {cst['outstanding']:>12,.2f}  {cst['max_days_overdue']}d")
    c.save()
    return buf.getvalue()
