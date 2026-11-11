from functools import cache

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agent import config
from agent.prompts.plan_generation import SYSTEM_PROMPT, build_user_prompt


# -----------------------------------------
# LLM Initialization
# -----------------------------------------
@cache
def _get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=config.GEMINI_MODEL,
        temperature=config.LLM_TEMPERATURE,
    )


# -----------------------------------------
# HCL Fence Cleanup
# -----------------------------------------
def _clean_hcl(text: str) -> str:
    # Models sometimes wrap output in ```hcl fences despite being told not to.
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    end = -1 if lines[-1].strip() == "```" else len(lines)
    return "\n".join(lines[1:end]).strip()


# -----------------------------------------
# Plan Generation Node
# -----------------------------------------
def generate_plan(state: dict) -> dict:
    alert = state.get("alert", {})
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=build_user_prompt(alert)),
    ]
    try:
        plan = _clean_hcl(_get_llm().invoke(messages).content)
        if not plan:
            return {"terraform_plan": "", "error": "Agent returned an empty Terraform plan"}
        return {"terraform_plan": plan}
    except Exception as e:
        return {"error": f"Plan generation failed: {e}"}
