from typing import Any, TypedDict


class OperationsState(TypedDict, total=False):
    run_id: str
    organization_id: str
    user_id: str
    role: str
    request: str
    intent: str
    execution_plan: dict
    retrieved_data: list
    total_outstanding: float
    payment_history: dict
    priorities: list
    skipped: list
    analysis_summary: str
    guidelines: list
    proposed_actions: list
    approval_id: str | None
    approval_status: str
    approved_email_ids: list
    execution_results: list
    report: dict
    errors: list
