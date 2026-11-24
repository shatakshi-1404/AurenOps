import random
from datetime import date, timedelta

from sqlalchemy import select

from app.core.db import session_scope
from app.core.security import hash_password
from app.models import Customer, Document, Invoice, Membership, Organization, User
from app.rag.ingest import ingest_document
from app.services.bootstrap import seed_org_defaults
from app.services.demo_data import GUIDELINES, NAMES, POLICY

if __name__ == "__main__":
    random.seed(7)
    with session_scope() as db:
        if db.scalar(select(Organization).where(Organization.slug == "demo-corp")):
            print("already seeded")
            raise SystemExit
        org = Organization(name="Demo Corp", slug="demo-corp", settings={})
        db.add(org)
        db.flush()
        for email, role in [("owner@demo.com", "owner"), ("admin@demo.com", "admin"),
                            ("operator@demo.com", "operator"), ("viewer@demo.com", "viewer")]:
            u = User(email=email, full_name=role.title() + " User", password_hash=hash_password("Passw0rd!"))
            db.add(u)
            db.flush()
            db.add(Membership(org_id=org.id, user_id=u.id, role=role))
        seed_org_defaults(db, org.id)
        today = date.today()
        for i, nm in enumerate(NAMES):
            c = Customer(org_id=org.id, name=nm, company=nm, email=f"billing{i}@{nm.split()[0].lower()}.example",
                         tier=random.choice(["standard", "standard", "premium"]))
            db.add(c)
            db.flush()
            for k in range(3):  # history: paid invoices (some late)
                due = today - timedelta(days=random.randint(120, 300))
                amt = random.randint(10, 90) * 1000
                db.add(Invoice(org_id=org.id, customer_id=c.id, number=f"INV-H{i:02d}{k}", amount=amt, amount_paid=amt,
                               issued_at=due - timedelta(days=30), due_date=due, status="paid",
                               paid_at=due + timedelta(days=random.randint(0, 35))))
            for k in range(random.randint(1, 3)):  # overdue / open
                days = random.choice([5, 12, 20, 28, 35, 47, 63, 80, 95, 130])
                amt = random.randint(8, 150) * 1000
                db.add(Invoice(org_id=org.id, customer_id=c.id, number=f"INV-{1000 + i * 10 + k}", amount=amt,
                               amount_paid=0, issued_at=today - timedelta(days=days + 30),
                               due_date=today - timedelta(days=days), status="overdue",
                               reminders_sent=random.choice([0, 0, 1, 2]),
                               last_reminder_at=today - timedelta(days=random.choice([1, 7, 14])) if random.random() < .3 else None))
        db.flush()
        for fn, cat, text in [("communication_guidelines.txt", "communication", GUIDELINES),
                              ("invoice_policy.txt", "policy", POLICY)]:
            d = Document(org_id=org.id, filename=fn, category=cat, content_type="text/plain", status="processing")
            db.add(d)
            db.flush()
            ingest_document(db, d, text.encode())
    print("Seeded. Login: operator@demo.com / Passw0rd!  (also owner@, admin@, viewer@)")
