# -----------------------------------------
# Agent State Schema
# -----------------------------------------
from typing import TypedDict


class AgentState(TypedDict, total=False):
    raw_alert: dict
    alert: dict
    terraform_plan: str
    remediation_summary: str
    risk_score: str
    validation_passed: bool
    risk_reason: str
    error: str | None
