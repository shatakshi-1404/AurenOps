from langgraph.graph import END, START, StateGraph

from app.agents import nodes as n
from app.workflows.state import OperationsState


def _after_orch(s):
    return "finalize" if s.get("intent") == "unknown" else "data_agent"


def _after_analysis(s):
    return "communication_agent" if s.get("intent") == "invoice_collection" else "reporting_agent"


def _after_compliance(s):
    if not s.get("proposed_actions"):
        return "reporting_agent"
    return "execution" if s.get("approval_status") == "approved" else "approval_gate"


def _after_gate(s):
    return "execution" if s.get("approval_status") == "approved" else "finalize"


def build_graph(checkpointer):
    g = StateGraph(OperationsState)
    g.add_node("orchestrator", n.orchestrator_node)
    g.add_node("data_agent", n.data_agent_node)
    g.add_node("analysis_agent", n.analysis_agent_node)
    g.add_node("communication_agent", n.communication_agent_node)
    g.add_node("compliance_agent", n.compliance_agent_node)
    g.add_node("approval_gate", n.approval_gate_node)
    g.add_node("execution", n.execution_node)
    g.add_node("reporting_agent", n.reporting_agent_node)
    g.add_node("finalize", n.finalize_node)

    g.add_edge(START, "orchestrator")
    g.add_conditional_edges("orchestrator", _after_orch, {"data_agent": "data_agent", "finalize": "finalize"})
    g.add_edge("data_agent", "analysis_agent")
    g.add_conditional_edges("analysis_agent", _after_analysis,
                            {"communication_agent": "communication_agent", "reporting_agent": "reporting_agent"})
    g.add_edge("communication_agent", "compliance_agent")
    g.add_conditional_edges("compliance_agent", _after_compliance,
                            {"approval_gate": "approval_gate", "execution": "execution", "reporting_agent": "reporting_agent"})
    g.add_conditional_edges("approval_gate", _after_gate, {"execution": "execution", "finalize": "finalize"})
    g.add_edge("execution", "reporting_agent")
    g.add_edge("reporting_agent", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)
