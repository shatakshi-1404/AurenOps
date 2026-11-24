import types
import uuid

import pytest

from app.agents.planner import classify_rules
from app.agents.nodes import score_invoice, template_email, _grounded
from app.rag.embeddings import embed_texts
from app.services.approvals import draft_hash
from app.services.policy import approver_allowed, get_policy


def D(body="hi"):
    return types.SimpleNamespace(id=uuid.UUID(int=1), to_email="a@b.c", subject="s", body=body)


def test_policy_defaults_and_override():
    assert get_policy({}, "read_invoice")["mode"] == "auto"
    assert get_policy({}, "send_email")["mode"] == "approval"
    assert get_policy({}, "delete_customer")["mode"] == "restricted"
    # refund can never be downgraded to auto
    assert get_policy({"policies": {"issue_refund": {"mode": "auto"}}}, "issue_refund")["mode"] == "approval"
    assert not approver_allowed(get_policy({}, "issue_refund"), "operator")


def test_approval_hash_binds_content():
    assert draft_hash([D()]) == draft_hash([D()])
    assert draft_hash([D()]) != draft_hash([D("edited after approval")])


def test_intent_rules():
    assert classify_rules("Find overdue invoices and draft client reminder emails") == "invoice_collection"
    assert classify_rules("Show me overdue invoices") == "overdue_report"
    assert classify_rules("What's the weather") == "unknown"


def test_scoring_and_grounding():
    inv = {"days_overdue": 100, "outstanding": 150000, "reminders_sent": 2, "number": "INV-1", "customer_name": "X",
           "due_date": "2026-01-01", "invoice_number": "INV-1"}
    sc, tier = score_invoice(inv, {"avg_days_late": 20})
    assert tier == "high" and sc > 60
    mail = template_email({**inv, "tier": tier}, "Demo")
    assert _grounded(mail["body"], inv)
    assert not _grounded("pay soon", inv)


def test_embedding_dim_and_norm():
    v = embed_texts(["overdue invoice reminder"])[0]
    assert len(v) == 384 and abs(sum(x * x for x in v) - 1) < 1e-6


@pytest.mark.skipif(True, reason="needs Postgres+Redis: remove skip when running against a test DB")
def test_tenant_isolation(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    import app.api.v1.operations as ops
    monkeypatch.setattr(ops, "enqueue_start", lambda *a, **k: None)
    c = TestClient(app)
    mk = lambda n: c.post("/api/v1/auth/register", json={"email": f"{n}-{uuid.uuid4().hex[:6]}@x.com",
                          "password": "Passw0rd!", "full_name": n, "org_name": n + " Org"}).json()["access_token"]
    a, b = mk("a"), mk("b")
    run = c.post("/api/v1/operations", json={"request": "find overdue invoices"}, headers={"Authorization": f"Bearer {a}"}).json()
    assert c.get(f"/api/v1/operations/{run['id']}", headers={"Authorization": f"Bearer {b}"}).status_code == 404
