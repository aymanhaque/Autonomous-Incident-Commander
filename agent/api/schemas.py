from pydantic import BaseModel
from typing import Any, Optional


class PlanRequest(BaseModel):
    alerts: list[dict[str, Any]]


class PlanResponse(BaseModel):
    terraform_plan: str
    plan_hash: Optional[str] = None  # "sha256:<hexdigest>" of terraform_plan
    remediation_summary: Optional[str] = None
    risk_score: str                 # "Low" | "Medium" | "High"
    validation_passed: bool = False
    risk_reason: Optional[str] = None
    alert_name: Optional[str] = None
    error: Optional[str] = None
 