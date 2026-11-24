import re

from app.agents.llm import llm_json

STEP = lambda key, agent, desc: {"key": key, "agent": agent, "description": desc}  # noqa: E731

INTENTS = {
    "invoice_collection": [
        STEP("orchestrator", "Orchestrator", "Understand request and plan"),
        STEP("data_agent", "Data Agent", "Retrieve overdue invoices"),
        STEP("analysis_agent", "Analysis Agent", "Prioritize overdue clients"),
        STEP("communication_agent", "Communication Agent", "Generate personalized email drafts"),
        STEP("compliance_agent", "Compliance Agent", "Check policy and create approval request"),
        STEP("approval_gate", "Human Approval", "Await human review"),
        STEP("execution", "Communication Agent", "Send approved emails and verify"),
        STEP("reporting_agent", "Reporting Agent", "Generate collection report"),
        STEP("finalize", "Orchestrator", "Finalize and audit"),
    ],
    "overdue_report": [
        STEP("orchestrator", "Orchestrator", "Understand request and plan"),
        STEP("data_agent", "Data Agent", "Retrieve overdue invoices"),
        STEP("analysis_agent", "Analysis Agent", "Prioritize overdue clients"),
        STEP("reporting_agent", "Reporting Agent", "Generate collection report"),
        STEP("finalize", "Orchestrator", "Finalize and audit"),
    ],
}


def classify_rules(text: str) -> str:
    t = text.lower()
    wants_email = any(w in t for w in ("email", "remind", "follow-up", "follow up", "followup", "draft", "collection"))
    about_invoices = any(w in t for w in ("invoice", "overdue", "unpaid", "payment", "collect"))
    if about_invoices and wants_email:
        return "invoice_collection"
    if about_invoices or "report" in t:
        return "overdue_report"
    return "unknown"


def _int(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def make_plan(org_id, run_id, request: str) -> dict:
    """LLM may only choose an intent + bounded params. Steps come from code, never from the model."""
    raw = llm_json(
        org_id, run_id,
        "You classify business requests for an invoice operations system. Reply JSON: "
        '{"intent": "invoice_collection|overdue_report|unknown", "min_days_overdue": int, '
        '"min_amount": number, "max_drafts": int}. invoice_collection = find overdue invoices AND '
        "prepare/send follow-up emails; overdue_report = only look up/report overdue invoices.",
        request, node="orchestrator")
    intent, source = None, "rules"
    params = {"min_days_overdue": 1, "min_amount": 0.0, "max_drafts": 20}
    if isinstance(raw, dict) and raw.get("intent") in (*INTENTS, "unknown"):
        intent, source = raw["intent"], "llm"
        params["min_days_overdue"] = _int(raw.get("min_days_overdue"), 1, 365, 1)
        params["max_drafts"] = _int(raw.get("max_drafts"), 1, 50, 20)
        try:
            params["min_amount"] = max(0.0, float(raw.get("min_amount") or 0))
        except (TypeError, ValueError):
            pass
    if not intent:
        intent = classify_rules(request)
        m = re.search(r"(\d+)\s*\+?\s*days", request.lower())
        if m:
            params["min_days_overdue"] = _int(m.group(1), 1, 365, 1)
    return {"intent": intent, "params": params, "source": source, "steps": INTENTS.get(intent, [])}
