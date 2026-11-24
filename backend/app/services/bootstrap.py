from sqlalchemy import select

import app.tools.business  # noqa: F401  (registers tools)
from app.models import Agent, Tool
from app.tools.registry import REGISTRY

AGENTS = [
    ("orchestrator", "Orchestrator Agent", "Understands requests and delegates work"),
    ("data_agent", "Data Agent", "Retrieves CRM and invoice information"),
    ("analysis_agent", "Analysis Agent", "Prioritizes customers and identifies patterns"),
    ("communication_agent", "Communication Agent", "Creates personalized email drafts"),
    ("reporting_agent", "Reporting Agent", "Generates operational reports"),
    ("compliance_agent", "Compliance Agent", "Checks permissions and policy requirements"),
]


def seed_org_defaults(db, org_id):
    have = {a.key for a in db.scalars(select(Agent).where(Agent.org_id == org_id))}
    for key, name, desc in AGENTS:
        if key not in have:
            db.add(Agent(org_id=org_id, key=key, name=name, description=desc))
    have_t = {t.name for t in db.scalars(select(Tool).where(Tool.org_id == org_id))}
    for spec in REGISTRY.values():
        if spec.name not in have_t:
            db.add(Tool(org_id=org_id, name=spec.name, description=spec.description, min_role=spec.min_role,
                        side_effect=spec.side_effect, policy_action=spec.policy_action))
    db.flush()
