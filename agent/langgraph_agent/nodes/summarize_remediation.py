# -----------------------------------------
# Remediation Summary Node
# -----------------------------------------
from langchain_core.messages import SystemMessage, HumanMessage

from agent.langgraph_agent.nodes.generate_plan import _get_llm
from agent.prompts.remediation_summary import SUMMARY_SYSTEM_PROMPT, build_summary_prompt


def summarize_remediation(state: dict) -> dict:
    alert = state.get("alert", {})
    plan = state.get("terraform_plan", "")
    if not plan:
        return {"remediation_summary": ""}

    messages = [
        SystemMessage(content=SUMMARY_SYSTEM_PROMPT),
        HumanMessage(content=build_summary_prompt(alert, plan)),
    ]
    try:
        response = _get_llm().invoke(messages)
        return {"remediation_summary": response.content.strip()}
    except Exception as e:
        # Best-effort: a failed summary should never block an otherwise-valid
        # plan, so this does not set `error` (which would hard-stop the graph).
        return {"remediation_summary": f"Summary unavailable: {e}"}
