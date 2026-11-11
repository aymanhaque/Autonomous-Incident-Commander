# -----------------------------------------
# Routing Logic — Hard Stop vs. Continue
# -----------------------------------------
def should_hard_stop(state: dict) -> str:
    return "hard_stop" if state.get("risk_score") == "High" else "continue"
