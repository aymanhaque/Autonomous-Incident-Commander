from langgraph.graph import StateGraph, START, END

from agent.langgraph_agent.state import AgentState
from agent.langgraph_agent.nodes.parse_alert import parse_alert
from agent.langgraph_agent.nodes.generate_plan import generate_plan
from agent.langgraph_agent.nodes.summarize_remediation import summarize_remediation
from agent.langgraph_agent.nodes.validate_plan import validate_plan
from agent.langgraph_agent.nodes.classify_risk import classify_risk
from agent.langgraph_agent.routing import should_hard_stop


# -----------------------------------------
# Hard Stop Node
# -----------------------------------------
def _hard_stop(state: dict) -> dict:
    return {"error": f"Hard stop: High-risk plan cannot be approved. Reason: {state.get('risk_reason', '')}"}


# -----------------------------------------
# Graph Construction
# -----------------------------------------
def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("parse_alert", parse_alert)
    builder.add_node("generate_plan", generate_plan)
    builder.add_node("summarize_remediation", summarize_remediation)
    builder.add_node("validate_plan", validate_plan)
    builder.add_node("classify_risk", classify_risk)
    builder.add_node("hard_stop", _hard_stop)

    builder.add_edge(START, "parse_alert")
    builder.add_edge("parse_alert", "generate_plan")
    builder.add_edge("generate_plan", "summarize_remediation")
    builder.add_edge("summarize_remediation", "validate_plan")
    builder.add_edge("validate_plan", "classify_risk")
    builder.add_conditional_edges(
        "classify_risk",
        should_hard_stop,
        {"hard_stop": "hard_stop", "continue": END},
    )
    builder.add_edge("hard_stop", END)

    return builder.compile()

graph = build_graph()
