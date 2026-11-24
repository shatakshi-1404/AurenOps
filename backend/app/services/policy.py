from app.core.roles import ROLE_RANK

DEFAULT_POLICIES = {
    "read_invoice": {"mode": "auto", "risk": "low"},
    "generate_report": {"mode": "auto", "risk": "low"},
    "draft_email": {"mode": "auto", "risk": "low"},
    "send_email": {"mode": "approval", "risk": "medium", "approver_min_role": "operator"},
    "change_invoice_status": {"mode": "approval", "risk": "high", "approver_min_role": "admin"},
    "delete_customer": {"mode": "restricted", "risk": "high"},
    "issue_refund": {"mode": "approval", "risk": "high", "approver_min_role": "admin"},
}
NEVER_AUTO = {"delete_customer", "issue_refund"}


def get_policy(org_settings: dict | None, action: str) -> dict:
    base = dict(DEFAULT_POLICIES.get(action, {"mode": "approval", "risk": "high", "approver_min_role": "admin"}))
    override = ((org_settings or {}).get("policies") or {}).get(action)
    if override:
        base.update({k: v for k, v in override.items() if v})
    if action in NEVER_AUTO and base["mode"] == "auto":
        base["mode"] = "approval"
    return base


def approver_allowed(policy: dict, role: str) -> bool:
    return ROLE_RANK[role] >= ROLE_RANK[policy.get("approver_min_role", "operator")]
