import json
import time
import uuid
from datetime import date

from langgraph.types import interrupt
from sqlalchemy import select

import app.tools.business  # noqa: F401
from app.agents.llm import llm_json, llm_text
from app.agents.planner import make_plan
from app.agents.tracking import tracked
from app.core.db import session_scope
from app.core.errors import PolicyViolation
from app.integrations.email import TransientProviderError
from app.models import AgentRun, Approval, EmailDraft, Membership, Notification, Organization, Report
from app.rag.search import hybrid_search
from app.services.approvals import draft_hash, get_or_create_approval, load_drafts
from app.services.audit import audit
from app.services.events import emit_event, set_run_status
from app.services.policy import approver_allowed, get_policy
from app.tools.registry import ToolContext, call_tool

COOLDOWN_DAYS = 3


def _ctx(db, s, approved=False, role=None):
    return ToolContext(db=db, org_id=uuid.UUID(s["organization_id"]), user_id=uuid.UUID(s["user_id"]),
                       role=role or s["role"], run_id=uuid.UUID(s["run_id"]), approved=approved)


# ───────────── Orchestrator ─────────────
@tracked("orchestrator", "orchestrator", status="PLANNING", input_keys=("request",))
def orchestrator_node(s):
    plan = make_plan(s["organization_id"], s["run_id"], s["request"])
    with session_scope() as db:
        run = db.get(AgentRun, uuid.UUID(s["run_id"]))
        run.intent, run.plan = plan["intent"], plan
    out = {"intent": plan["intent"], "execution_plan": plan}
    if plan["intent"] == "unknown":
        out["errors"] = ["No supported workflow matches this request."]
    return out


# ───────────── Data Agent ─────────────
@tracked("data_agent", "data_agent", input_keys=("execution_plan",))
def data_agent_node(s):
    p = s["execution_plan"]["params"]
    with session_scope() as db:
        ctx = _ctx(db, s)
        res = call_tool(ctx, "get_overdue_invoices",
                        {"min_days_overdue": p["min_days_overdue"], "min_amount": p["min_amount"]})
        history = {cid: call_tool(ctx, "get_customer_payment_history", {"customer_id": cid})
                   for cid in list({i["customer_id"] for i in res["invoices"]})[:50]}
    return {"retrieved_data": res["invoices"], "total_outstanding": res["total_outstanding"],
            "payment_history": history}


# ───────────── Analysis Agent (deterministic scoring) ─────────────
def score_invoice(inv: dict, hist: dict | None) -> tuple[float, str]:
    sc = min(inv["days_overdue"], 120) / 120 * 50 + min(inv["outstanding"], 200_000) / 200_000 * 35
    sc += 5 if inv["reminders_sent"] >= 2 else 0
    sc += 10 if hist and (hist.get("avg_days_late") or 0) > 15 else 0
    return round(sc, 1), ("high" if sc >= 60 else "medium" if sc >= 35 else "low")


@tracked("analysis_agent", "analysis_agent", input_keys=("total_outstanding",))
def analysis_agent_node(s):
    today, pri, skipped = date.today(), [], []
    for inv in s.get("retrieved_data", []):
        last = inv.get("last_reminder_at")
        if last and (today - date.fromisoformat(last)).days < COOLDOWN_DAYS:
            skipped.append({**inv, "skip_reason": f"reminded within last {COOLDOWN_DAYS} days"})
            continue
        sc, tier = score_invoice(inv, s.get("payment_history", {}).get(inv["customer_id"]))
        pri.append({**inv, "score": sc, "tier": tier})
    pri.sort(key=lambda x: -x["score"])
    facts = {"count": len(pri), "high": sum(p["tier"] == "high" for p in pri), "skipped": len(skipped),
             "total_outstanding": s.get("total_outstanding")}
    summary = llm_text(s["organization_id"], s["run_id"],
                       "Summarize these invoice-collection numbers in 2 sentences. Use ONLY the given numbers.",
                       json.dumps(facts), node="analysis_agent") or (
        f"{facts['count']} overdue invoices to contact ({facts['high']} high priority), "
        f"{facts['skipped']} skipped (recently reminded). Total outstanding ₹{facts['total_outstanding']:,.2f}.")
    return {"priorities": pri, "skipped": skipped, "analysis_summary": summary}


# ───────────── Communication Agent ─────────────
def _fmt(x):
    return f"{x:,.2f}"


def template_email(p: dict, org_name: str) -> dict:
    tone = {"high": "We urgently need to resolve this balance.",
            "medium": "We would appreciate settling this at your earliest convenience.",
            "low": "A gentle reminder in case this slipped through."}[p["tier"]]
    return {"subject": f"Payment reminder: invoice {p['invoice_number']} ({p['days_overdue']} days overdue)",
            "body": (f"Hello {p['customer_name']},\n\nOur records show invoice {p['invoice_number']} with an outstanding "
                     f"balance of ₹{_fmt(p['outstanding'])} was due on {p['due_date']} and is now {p['days_overdue']} "
                     f"days overdue. {tone}\n\nIf you have already paid, please ignore this note or reply with the "
                     f"payment reference.\n\nRegards,\nAccounts Team, {org_name}")}


def _grounded(body: str, p: dict) -> bool:
    return p["invoice_number"] in body and _fmt(p["outstanding"]) in body


@tracked("communication_agent", "communication_agent", input_keys=("priorities",))
def communication_agent_node(s):
    max_n = s["execution_plan"]["params"]["max_drafts"]
    targets = s.get("priorities", [])[:max_n]
    actions, cites = [], []
    with session_scope() as db:
        org = db.get(Organization, uuid.UUID(s["organization_id"]))
        guides = hybrid_search(db, org.id, s["role"],
                               "customer communication guidelines overdue invoice reminder tone", k=3)
        cites = [g["citation"] for g in guides]
        guide_text = "\n".join(g["content"][:600] for g in guides)
        ctx = _ctx(db, s)
        for p in targets:
            p = {**p, "invoice_number": p["number"]}
            draft = None
            if guide_text:
                raw = llm_json(s["organization_id"], s["run_id"],
                               "You write polite, professional invoice reminder emails following the company "
                               "guidelines. Reply JSON {\"subject\":str,\"body\":str}. The body MUST include the exact "
                               "invoice number and the exact outstanding amount given. Do not invent facts, discounts "
                               "or deadlines.\nGUIDELINES:\n" + guide_text,
                               json.dumps({k: p[k] for k in ("customer_name", "invoice_number", "outstanding",
                                                              "days_overdue", "due_date", "tier")}, default=str),
                               node="communication_agent")
                if isinstance(raw, dict) and isinstance(raw.get("body"), str) and _grounded(raw["body"], p):
                    draft = {"subject": str(raw.get("subject") or "")[:280] or f"Invoice {p['number']} reminder",
                             "body": raw["body"]}
            if not draft:  # LLM missing, or it dropped/invented a figure
                draft = template_email(p, org.name)
            res = call_tool(ctx, "create_email_draft", {"customer_id": p["customer_id"], "invoice_id": p["invoice_id"],
                                                        "subject": draft["subject"], "body": draft["body"]})
            actions.append({"type": "send_email", "email_id": res["email_id"], "to": res["to"],
                            "subject": res["subject"], "invoice_number": p["number"], "invoice_id": p["invoice_id"],
                            "customer": p["customer_name"], "outstanding": p["outstanding"],
                            "days_overdue": p["days_overdue"], "tier": p["tier"],
                            "reminders_sent": p["reminders_sent"]})
    return {"proposed_actions": actions, "guidelines": cites}


# ───────────── Compliance Agent ─────────────
@tracked("compliance_agent", "compliance_agent", input_keys=("proposed_actions",))
def compliance_agent_node(s):
    actions = s.get("proposed_actions", [])
    if not actions:
        return {"approval_id": None, "approval_status": "none"}
    with session_scope() as db:
        org = db.get(Organization, uuid.UUID(s["organization_id"]))
        pol = get_policy(org.settings, "send_email")
        if pol["mode"] == "restricted":
            return {"approval_id": None, "approval_status": "none", "proposed_actions": [],
                    "errors": s.get("errors", []) + ["send_email is restricted by policy"]}
        drafts = load_drafts(db, org.id, [a["email_id"] for a in actions])
        auto = pol["mode"] == "auto"
        a = get_or_create_approval(db, org_id=org.id, run_id=uuid.UUID(s["run_id"]), drafts=drafts,
                                   items=actions, policy=pol, auto=auto)
        if auto:
            for d in drafts:
                d.status = "approved"
        audit(db, org.id, uuid.UUID(s["user_id"]), "approval.requested" if not auto else "approval.auto",
              "approval", a.id, uuid.UUID(s["run_id"]), {"risk": a.risk, "count": len(drafts)})
        aid, status = str(a.id), a.status
    if not auto:
        emit_event(s["organization_id"], s["run_id"], "approval.requested", "compliance_agent", "pending",
                   {"approval_id": aid, "count": len(actions)})
    return {"approval_id": aid, "approval_status": "approved" if auto else "pending",
            "approved_email_ids": [a["email_id"] for a in actions] if auto else []}


# ───────────── Human-in-the-loop gate ─────────────
@tracked("approval_gate", "compliance_agent", status="WAITING_FOR_APPROVAL", max_attempts=1)
def approval_gate_node(s):
    # First pass: raises GraphInterrupt (state is checkpointed to Postgres).
    # Resume pass: interrupt() returns the value passed via Command(resume=...).
    decision = interrupt({"type": "approval_required", "approval_id": s["approval_id"]})
    ok = decision.get("decision") == "approved"
    if ok:
        set_run_status(s["organization_id"], s["run_id"], "APPROVED")
    return {"approval_status": decision.get("decision", "rejected"),
            "approved_email_ids": decision.get("approved_email_ids", [])}


# ───────────── Execution: execute -> verify ─────────────
def audit_fail(s, msg):
    with session_scope() as db:
        audit(db, uuid.UUID(s["organization_id"]), uuid.UUID(s["user_id"]), "approval.invalidated",
              "approval", s.get("approval_id"), uuid.UUID(s["run_id"]), {"reason": msg})


@tracked("execution", "communication_agent", status="EXECUTING", max_attempts=1)  # side effects: no blind retries
def execution_node(s):
    org_id, results = uuid.UUID(s["organization_id"]), []
    invalid = None
    run_ctx_role = "operator"
    with session_scope() as db:
        a = db.get(Approval, uuid.UUID(s["approval_id"]))
        org = db.get(Organization, org_id)
        pol = get_policy(org.settings, "send_email")
        if a.status != "approved":
            invalid = f"Approval is '{a.status}'"
        else:
            drafts = load_drafts(db, org_id, a.approved_ids or [])
            if draft_hash(drafts) != a.approved_hash:
                invalid = "Approved action changed after approval; approval invalidated"
            else:
                role = s["role"]
                if a.decided_by:
                    m = db.scalar(select(Membership).where(Membership.org_id == org_id, Membership.user_id == a.decided_by))
                    role = m.role if m else "viewer"
                if not approver_allowed(pol, role):
                    invalid = "Approver lacks the role required by policy at execution time"
                else:
                    run_ctx_role = role if role in ("operator", "admin", "owner") else "operator"
        if invalid:
            a.status = "invalidated"
            for d in db.scalars(select(EmailDraft).where(EmailDraft.id.in_([uuid.UUID(i) for i in (a.approved_ids or [])]))):
                if d.status == "approved":
                    d.status = "rejected"
        approved_ids = list(a.approved_ids or [])
    if invalid:
        audit_fail(s, invalid)
        raise PolicyViolation(invalid)

    for eid in approved_ids:
        for attempt in range(1, 4):  # retries ONLY for errors where provider guarantees nothing was sent
            try:
                with session_scope() as db:
                    ctx = _ctx(db, s, approved=True, role=run_ctx_role)
                    results.append(call_tool(ctx, "send_approved_email", {"email_id": eid}))
                break
            except TransientProviderError:
                if attempt == 3:
                    results.append({"email_id": eid, "status": "failed", "detail": "provider unavailable"})
                else:
                    time.sleep(0.5 * 2 ** attempt)

    set_run_status(s["organization_id"], s["run_id"], "VERIFYING")
    with session_scope() as db:  # verify: DB state matches what we think happened
        statuses = {str(d.id): d.status for d in load_drafts(db, org_id, approved_ids)}
        audit(db, org_id, uuid.UUID(s["user_id"]), "execution.verified", "approval", uuid.UUID(s["approval_id"]),
              uuid.UUID(s["run_id"]), {"sent": sum(v == "sent" for v in statuses.values()), "total": len(statuses)})
    return {"execution_results": results}


# ───────────── Reporting ─────────────
@tracked("reporting_agent", "reporting_agent")
def reporting_agent_node(s):
    with session_scope() as db:
        res = call_tool(_ctx(db, s), "generate_collection_report", {"kind": "collection"})
        rid = res["report_id"]
    facts = {k: res["summary"][k] for k in ("overdue_invoice_count", "total_outstanding", "aging")}
    facts["run_actions"] = res["summary"].get("run_actions", {})
    narrative = llm_text(s["organization_id"], s["run_id"],
                         "Write a 3-sentence collections status note. Use ONLY the numbers provided; do not invent any.",
                         json.dumps(facts, default=str), node="reporting_agent")
    if not narrative:
        narrative = (f"{facts['overdue_invoice_count']} invoices remain overdue totalling "
                     f"₹{facts['total_outstanding']:,.2f}. Email outcomes: {facts['run_actions'].get('email_status_counts', {})}.")
    with session_scope() as db:
        rep = db.get(Report, uuid.UUID(rid))
        rep.summary = {**rep.summary, "narrative": narrative}
    return {"report": {"report_id": rid, "narrative": narrative}}


# ───────────── Finalize ─────────────
@tracked("finalize", "orchestrator", status=None, max_attempts=1)
def finalize_node(s):
    org, run_id = s["organization_id"], s["run_id"]
    status = s.get("approval_status")
    if s.get("intent") == "unknown":
        set_run_status(org, run_id, "FAILED", error="; ".join(s.get("errors", [])) or "Unsupported request")
        emit_event(org, run_id, "run.failed", None, "FAILED", {})
    elif status in ("rejected", "expired"):
        set_run_status(org, run_id, "REJECTED", error=f"Approval {status}")
        emit_event(org, run_id, "run.rejected", None, "REJECTED", {"reason": status})
    else:
        res = s.get("execution_results", [])
        result = {"intent": s.get("intent"), "analysis": s.get("analysis_summary"),
                  "drafts": len(s.get("proposed_actions", [])),
                  "sent": sum(r["status"] == "sent" for r in res), "failed": sum(r["status"] == "failed" for r in res),
                  "unknown": sum(r["status"] == "unknown" for r in res),
                  "report_id": (s.get("report") or {}).get("report_id"), "guidelines": s.get("guidelines", [])}
        set_run_status(org, run_id, "COMPLETED", result=result)
        emit_event(org, run_id, "run.completed", None, "COMPLETED", result)
    with session_scope() as db:
        audit(db, uuid.UUID(org), uuid.UUID(s["user_id"]), "run.finished", "agent_run", run_id, uuid.UUID(run_id),
              {"approval_status": status})
        db.add(Notification(org_id=uuid.UUID(org), user_id=uuid.UUID(s["user_id"]), title="Operation finished",
                            body=s["request"][:120], link=f"/operations/{run_id}"))
    return {}
