# -----------------------------------------
# Risk Classification Node
# -----------------------------------------
from agent.risk_validator.blast_radius import classify

def classify_risk(state: dict) -> dict:
    risk_score, risk_reason = classify(state.get("terraform_plan", ""), state.get("alert"))
    return {"risk_score": risk_score, "risk_reason": risk_reason}
