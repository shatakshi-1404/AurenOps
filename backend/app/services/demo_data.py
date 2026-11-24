import random
from datetime import date, timedelta

from sqlalchemy import func, select

from app.core.errors import AppError
from app.models import Customer, Document, Invoice
from app.rag.ingest import ingest_document

GUIDELINES = """Customer Communication Guidelines for Overdue Invoices.
Always address the customer by name and stay polite, calm and professional. Never threaten or use aggressive language.
State the invoice number and the exact outstanding amount. Mention the original due date and how many days overdue.
For customers 1-30 days overdue use a friendly reminder tone. For 31-60 days use a firm but courteous tone.
For 60+ days ask for a payment date or a call. Offer to resend the invoice copy. Never promise discounts or waive fees.
Close with the sender's team name and invite the customer to reply if payment was already made."""

POLICY = """Invoice Policy. Payment terms are net 30 days. Reminders may be sent at most once every 3 days per invoice.
Invoices over 90 days overdue are escalated to the finance manager. Refunds require admin approval.
Customer records may only be deleted by the owner and never through automation."""

NAMES = ["Acme Traders", "Bluepeak Logistics", "Cedar Foods", "Delta Fabrics", "Evergreen Clinics", "Fusion Labs",
         "Granite Builders", "Horizon Textiles", "Indus Pharma", "Jade Hotels", "Kiran Motors", "Lotus Retail",
         "Mehta Steel", "Nova Learning", "Orbit Cargo"]


def seed_demo_data(db, org_id) -> dict:
    if db.scalar(select(func.count()).select_from(Customer).where(Customer.org_id == org_id)):
        raise AppError(409, "already_has_data", "This organization already has customers")
    rnd, today = random.Random(7), date.today()
    for i, nm in enumerate(NAMES):
        c = Customer(org_id=org_id, name=nm, company=nm, email=f"billing{i}@{nm.split()[0].lower()}.example",
                     tier=rnd.choice(["standard", "standard", "premium"]))
        db.add(c)
        db.flush()
        for k in range(3):  # paid history, some late
            due = today - timedelta(days=rnd.randint(120, 300))
            amt = rnd.randint(10, 90) * 1000
            db.add(Invoice(org_id=org_id, customer_id=c.id, number=f"INV-H{i:02d}{k}", amount=amt, amount_paid=amt,
                           issued_at=due - timedelta(days=30), due_date=due, status="paid",
                           paid_at=due + timedelta(days=rnd.randint(0, 35))))
        for k in range(rnd.randint(1, 3)):  # overdue
            days = rnd.choice([5, 12, 20, 28, 35, 47, 63, 80, 95, 130])
            amt = rnd.randint(8, 150) * 1000
            db.add(Invoice(org_id=org_id, customer_id=c.id, number=f"INV-{1000 + i * 10 + k}", amount=amt,
                           amount_paid=0, issued_at=today - timedelta(days=days + 30),
                           due_date=today - timedelta(days=days), status="overdue",
                           reminders_sent=rnd.choice([0, 0, 1, 2])))
    db.flush()
    for fn, cat, text in [("communication_guidelines.txt", "communication", GUIDELINES),
                          ("invoice_policy.txt", "policy", POLICY)]:
        d = Document(org_id=org_id, filename=fn, category=cat, content_type="text/plain", status="processing")
        db.add(d)
        db.flush()
        ingest_document(db, d, text.encode())
    return {"customers": len(NAMES), "documents": 2}
