import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app.core.errors import ToolError
from app.integrations.email import PermanentProviderError, TransientProviderError, get_email_provider
from app.models import Customer, EmailDraft, Invoice, Report
from app.services.reports import create_report
from app.tools.registry import ToolContext, tool


def _uid(s):
    try:
        return uuid.UUID(str(s))
    except ValueError:
        raise ToolError(f"Invalid id: {s}")


def _outstanding(i: Invoice) -> float:
    return float(i.amount - i.amount_paid)


# ───────────── Invoice tools ─────────────
class OverdueIn(BaseModel):
    min_days_overdue: int = Field(1, ge=1, le=3650)
    min_amount: float = Field(0, ge=0)
    limit: int = Field(200, ge=1, le=1000)


class InvoiceRow(BaseModel):
    invoice_id: str
    number: str
    customer_id: str
    customer_name: str
    email: str
    amount: float
    outstanding: float
    due_date: date
    days_overdue: int
    reminders_sent: int
    last_reminder_at: Optional[date] = None


class OverdueOut(BaseModel):
    invoices: list[InvoiceRow]
    count: int
    total_outstanding: float


@tool("get_overdue_invoices", OverdueIn, OverdueOut)
def get_overdue_invoices(ctx: ToolContext, a: OverdueIn):
    """Return overdue, unpaid invoices for the organization."""
    today = date.today()
    rows = ctx.db.execute(
        select(Invoice, Customer).join(Customer, Customer.id == Invoice.customer_id)
        .where(Invoice.org_id == ctx.org_id, Invoice.status.in_(["open", "overdue"]),
               Invoice.due_date <= today - timedelta(days=a.min_days_overdue))
        .order_by(Invoice.due_date).limit(a.limit)
    ).all()
    out = []
    for inv, c in rows:
        o = _outstanding(inv)
        if o <= 0 or o < a.min_amount:
            continue
        out.append(InvoiceRow(invoice_id=str(inv.id), number=inv.number, customer_id=str(c.id),
                              customer_name=c.name, email=c.email, amount=float(inv.amount), outstanding=o,
                              due_date=inv.due_date, days_overdue=(today - inv.due_date).days,
                              reminders_sent=inv.reminders_sent, last_reminder_at=inv.last_reminder_at))
    return OverdueOut(invoices=out, count=len(out), total_outstanding=round(sum(i.outstanding for i in out), 2))


class InvoiceIdIn(BaseModel):
    invoice_id: str


class InvoiceDetailOut(BaseModel):
    invoice_id: str
    number: str
    customer_id: str
    amount: float
    outstanding: float
    status: str
    due_date: date
    reminders_sent: int


@tool("get_invoice_details", InvoiceIdIn, InvoiceDetailOut)
def get_invoice_details(ctx, a: InvoiceIdIn):
    """Fetch one invoice."""
    inv = ctx.db.scalar(select(Invoice).where(Invoice.id == _uid(a.invoice_id), Invoice.org_id == ctx.org_id))
    if not inv:
        raise ToolError("Invoice not found")
    return InvoiceDetailOut(invoice_id=str(inv.id), number=inv.number, customer_id=str(inv.customer_id),
                            amount=float(inv.amount), outstanding=_outstanding(inv), status=inv.status,
                            due_date=inv.due_date, reminders_sent=inv.reminders_sent)


class OutstandingIn(BaseModel):
    customer_id: Optional[str] = None


class OutstandingOut(BaseModel):
    total_outstanding: float
    invoice_count: int


@tool("calculate_outstanding_amount", OutstandingIn, OutstandingOut)
def calculate_outstanding_amount(ctx, a: OutstandingIn):
    """Deterministic SQL-side total of unpaid invoices."""
    q = select(Invoice).where(Invoice.org_id == ctx.org_id, Invoice.status.in_(["open", "overdue"]))
    if a.customer_id:
        q = q.where(Invoice.customer_id == _uid(a.customer_id))
    invs = [i for i in ctx.db.scalars(q) if _outstanding(i) > 0]
    return OutstandingOut(total_outstanding=round(sum(_outstanding(i) for i in invs), 2), invoice_count=len(invs))


class StatusIn(BaseModel):
    invoice_id: str
    status: str = Field(pattern="^(open|overdue|paid|void)$")


class StatusOut(BaseModel):
    invoice_id: str
    status: str


@tool("update_invoice_status", StatusIn, StatusOut, min_role="operator", side_effect=True,
      policy_action="change_invoice_status")
def update_invoice_status(ctx, a: StatusIn):
    """Change an invoice's status (approval required by policy)."""
    inv = ctx.db.scalar(select(Invoice).where(Invoice.id == _uid(a.invoice_id), Invoice.org_id == ctx.org_id))
    if not inv:
        raise ToolError("Invoice not found")
    inv.status = a.status
    if a.status == "paid":
        inv.paid_at = date.today()
        inv.amount_paid = inv.amount
    return StatusOut(invoice_id=str(inv.id), status=inv.status)


# ───────────── CRM tools ─────────────
class SearchCustIn(BaseModel):
    query: str = Field(min_length=1, max_length=100)


class CustomerOut(BaseModel):
    customer_id: str
    name: str
    company: str
    email: str
    tier: str


class SearchCustOut(BaseModel):
    customers: list[CustomerOut]


def _cust(c):
    return CustomerOut(customer_id=str(c.id), name=c.name, company=c.company, email=c.email, tier=c.tier)


@tool("search_customers", SearchCustIn, SearchCustOut)
def search_customers(ctx, a: SearchCustIn):
    """Search customers by name, company or email."""
    like = f"%{a.query}%"
    cs = ctx.db.scalars(select(Customer).where(
        Customer.org_id == ctx.org_id,
        or_(Customer.name.ilike(like), Customer.company.ilike(like), Customer.email.ilike(like))).limit(25))
    return SearchCustOut(customers=[_cust(c) for c in cs])


class CustIdIn(BaseModel):
    customer_id: str


@tool("get_customer_details", CustIdIn, CustomerOut)
def get_customer_details(ctx, a: CustIdIn):
    """Fetch one customer."""
    c = ctx.db.scalar(select(Customer).where(Customer.id == _uid(a.customer_id), Customer.org_id == ctx.org_id))
    if not c:
        raise ToolError("Customer not found")
    return _cust(c)


class HistoryOut(BaseModel):
    customer_id: str
    paid_invoices: int
    open_invoices: int
    avg_days_late: Optional[float] = None


@tool("get_customer_payment_history", CustIdIn, HistoryOut)
def get_customer_payment_history(ctx, a: CustIdIn):
    """Historic payment behaviour: how late this customer usually pays."""
    cid = _uid(a.customer_id)
    invs = list(ctx.db.scalars(select(Invoice).where(Invoice.org_id == ctx.org_id, Invoice.customer_id == cid)))
    paid = [i for i in invs if i.status == "paid" and i.paid_at]
    late = [(i.paid_at - i.due_date).days for i in paid]
    return HistoryOut(customer_id=a.customer_id, paid_invoices=len(paid),
                      open_invoices=len([i for i in invs if i.status in ("open", "overdue")]),
                      avg_days_late=round(sum(late) / len(late), 1) if late else None)


# ───────────── Email tools ─────────────
class DraftIn(BaseModel):
    customer_id: str
    invoice_id: str
    subject: Optional[str] = Field(None, max_length=300)
    body: Optional[str] = Field(None, max_length=8000)


class DraftOut(BaseModel):
    email_id: str
    to: str
    subject: str
    body: str
    status: str
    created: bool


@tool("create_email_draft", DraftIn, DraftOut, min_role="operator")
def create_email_draft(ctx, a: DraftIn):
    """Create (idempotently) a reminder email draft. Never sends."""
    inv = ctx.db.scalar(select(Invoice).where(Invoice.id == _uid(a.invoice_id), Invoice.org_id == ctx.org_id))
    cust = ctx.db.scalar(select(Customer).where(Customer.id == _uid(a.customer_id), Customer.org_id == ctx.org_id))
    if not inv or not cust or inv.customer_id != cust.id:
        raise ToolError("Invoice/customer mismatch")
    key = f"draft:{ctx.run_id or 'adhoc'}:{inv.id}"
    ex = ctx.db.scalar(select(EmailDraft).where(EmailDraft.idempotency_key == key))
    if ex:
        return DraftOut(email_id=str(ex.id), to=ex.to_email, subject=ex.subject, body=ex.body,
                        status=ex.status, created=False)
    subject = a.subject or f"Payment reminder: invoice {inv.number}"
    body = a.body or (f"Hello {cust.name},\n\nThis is a reminder that invoice {inv.number} "
                      f"(outstanding ₹{_outstanding(inv):,.2f}) was due on {inv.due_date}.\n\n"
                      "Please let us know if you have already paid.\n\nRegards,\nAccounts Team")
    d = EmailDraft(org_id=ctx.org_id, run_id=ctx.run_id, customer_id=cust.id, invoice_id=inv.id,
                   to_email=cust.email, subject=subject, body=body, original_subject=subject,
                   original_body=body, status="draft", idempotency_key=key)
    ctx.db.add(d)
    ctx.db.flush()
    return DraftOut(email_id=str(d.id), to=d.to_email, subject=subject, body=body, status="draft", created=True)


class EmailIdIn(BaseModel):
    email_id: str


@tool("preview_email", EmailIdIn, DraftOut)
def preview_email(ctx, a: EmailIdIn):
    """Preview a stored draft."""
    d = ctx.db.scalar(select(EmailDraft).where(EmailDraft.id == _uid(a.email_id), EmailDraft.org_id == ctx.org_id))
    if not d:
        raise ToolError("Draft not found")
    return DraftOut(email_id=str(d.id), to=d.to_email, subject=d.subject, body=d.body, status=d.status, created=False)


class SendOut(BaseModel):
    email_id: str
    status: str  # sent | failed | unknown
    detail: Optional[str] = None


@tool("send_approved_email", EmailIdIn, SendOut, min_role="operator", side_effect=True, policy_action="send_email")
def send_approved_email(ctx, a: EmailIdIn):
    """Send an APPROVED draft through the email provider (idempotent, no blind retries)."""
    d = ctx.db.scalar(select(EmailDraft).where(EmailDraft.id == _uid(a.email_id), EmailDraft.org_id == ctx.org_id)
                      .with_for_update())
    if not d:
        raise ToolError("Draft not found")
    if d.status == "sent":
        return SendOut(email_id=str(d.id), status="sent", detail="already sent")
    if d.status == "sending":
        # a previous attempt may or may not have delivered: DO NOT resend automatically
        return SendOut(email_id=str(d.id), status="unknown", detail="previous attempt outcome unknown")
    if d.status != "approved":
        raise ToolError(f"Draft is '{d.status}', not approved")
    d.status = "sending"
    ctx.db.commit()  # persist intent BEFORE the side effect
    provider = get_email_provider(ctx.db, ctx.org_id)
    try:
        mid = provider.send(d.to_email, d.subject, d.body, d.idempotency_key)
    except TransientProviderError:
        d.status = "approved"  # provider guarantees nothing was sent
        ctx.db.commit()
        raise
    except PermanentProviderError as e:
        d.status, d.error = "failed", str(e)
        ctx.db.commit()
        return SendOut(email_id=str(d.id), status="failed", detail=str(e))
    d.status, d.provider_message_id, d.sent_at = "sent", mid, datetime.now(timezone.utc)
    inv = ctx.db.get(Invoice, d.invoice_id)
    if inv:
        inv.reminders_sent += 1
        inv.last_reminder_at = date.today()
    return SendOut(email_id=str(d.id), status="sent", detail=mid)


# ───────────── Reporting tools ─────────────
class ReportIn(BaseModel):
    kind: str = "collection"


class ReportOut(BaseModel):
    report_id: str
    summary: dict


@tool("generate_collection_report", ReportIn, ReportOut, min_role="operator")
def generate_collection_report(ctx, a: ReportIn):
    """Deterministic SQL-computed collection report (numbers are never LLM-generated)."""
    rep = create_report(ctx.db, ctx.org_id, ctx.run_id, a.kind)
    return ReportOut(report_id=str(rep.id), summary=rep.summary)


class ReportIdIn(BaseModel):
    report_id: str


class CsvOut(BaseModel):
    csv: str


@tool("export_report_csv", ReportIdIn, CsvOut)
def export_report_csv(ctx, a: ReportIdIn):
    """Export a stored report as CSV."""
    rep = ctx.db.scalar(select(Report).where(Report.id == _uid(a.report_id), Report.org_id == ctx.org_id))
    if not rep:
        raise ToolError("Report not found")
    return CsvOut(csv=rep.csv)
