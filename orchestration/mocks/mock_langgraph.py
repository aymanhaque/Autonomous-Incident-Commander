"""Mock LangGraph plan-generation service (thin, deterministic).

Stands in for Jean-Pascal's real LangGraph agent so the whole approval loop can
run before it's finished. Given an alert payload, returns a CANNED response keyed
by ``alert_type``:

  * OOMKilled   -> Med  (memory bump; reversible)
  * 504         -> Low  (HPA/timeout tweak; reversible)
  * NodePressure-> Med  (cordon/drain-ish resource change)
  * DeleteNamespace (or any type in the destructive set) -> High (hard-stopped)

Contract: a destructive / high-blast alert type MUST return risk 'High'.
``plan_hash`` is the real sha256 of ``plan_inline`` so downstream tamper-evidence
checks are meaningful.

Run:  uvicorn mock_langgraph:app --port 8001
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="AIC Mock LangGraph", version="0.1.0")

# Alert types considered destructive / high blast radius -> always risk 'High'.
_DESTRUCTIVE = {
    "DeleteNamespace",
    "DropDatabase",
    "ScaleToZero",
    "DeletePVC",
    "NodeDrainAll",
}


class GeneratePlanRequest(BaseModel):
    # Lenient on purpose: the real agent gets a full Alertmanager payload. We only
    # need alert_type; everything else is echoed/ignored.
    model_config = ConfigDict(extra="allow")
    alert_type: str = Field(..., min_length=1)
    alert_payload: Optional[dict[str, Any]] = None
    alert_fingerprint: Optional[str] = None


def _canned(alert_type: str) -> tuple[str, str, str, str, str]:
    """Return (plan_inline, plan_summary, risk, risk_rationale, remediation_summary)."""
    if alert_type in _DESTRUCTIVE:
        return (
            'resource "null_resource" "blocked" { triggers = { note = "destructive" } }',
            f"Destructive remediation for {alert_type} -- requires manual sign-off",
            "High",
            "High blast radius / irreversible; hard-stopped, never auto-approved.",
            f"The {alert_type} alert indicates a destructive, high-blast-radius "
            "operation was requested. The proposed change is blocked pending "
            "manual SRE sign-off rather than auto-applied.",
        )
    if alert_type == "OOMKilled":
        return (
            'resource "kubernetes_deployment" "target" {\n'
            '  spec { template { spec { container { resources {\n'
            '    limits = { memory = "1Gi" }\n'
            "  } } } } }\n}",
            "Increase memory limit 512Mi -> 1Gi on the OOMKilled deployment",
            "Med",
            "Resource bump only; no traffic shift. Reversible.",
            "The container was killed for exceeding its memory limit. The "
            "proposed plan raises the deployment's memory limit from 512Mi to "
            "1Gi so the workload has enough headroom to run without being "
            "OOM-killed again.",
        )
    if alert_type == "504":
        return (
            'resource "kubernetes_horizontal_pod_autoscaler" "target" {\n'
            '  spec { max_replicas = 6 min_replicas = 3 }\n}',
            "Raise HPA max replicas 4 -> 6 to absorb latency-driving load",
            "Low",
            "Additive scale-out; easily reversible, no data path change.",
            "Upstream request timeouts (504s) suggest the service is "
            "under-provisioned for current load. The proposed plan raises the "
            "autoscaler's max replicas from 4 to 6 so it can scale out further "
            "before requests start timing out.",
        )
    if alert_type == "NodePressure":
        return (
            'resource "kubernetes_deployment" "target" {\n'
            '  spec { replicas = 2 }\n}',
            "Reduce noisy-neighbor replica count to relieve node memory pressure",
            "Med",
            "Rescheduling workload; brief capacity dip, reversible.",
            "The node is under memory pressure from a noisy-neighbor workload. "
            "The proposed plan reduces that deployment's replica count to free "
            "up memory on the node, at the cost of a brief capacity dip.",
        )
    # Unknown alert type: conservative default, still deterministic.
    return (
        'resource "null_resource" "noop" {}',
        f"No canned plan for alert_type={alert_type}; noop placeholder",
        "Med",
        "Unknown alert type; defaulting to a cautious reversible noop.",
        f"The alert type '{alert_type}' isn't recognized by this mock, so no "
        "concrete remediation could be generated. A no-op placeholder plan is "
        "returned instead of guessing at a fix.",
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate-plan")
def generate_plan(req: GeneratePlanRequest):
    plan_inline, plan_summary, risk, risk_rationale, remediation_summary = _canned(req.alert_type)
    plan_hash = "sha256:" + hashlib.sha256(plan_inline.encode("utf-8")).hexdigest()
    return {
        "plan_format": "hcl",
        "plan_inline": plan_inline,
        "plan_summary": plan_summary,
        "plan_hash": plan_hash,
        "risk": risk,
        "risk_rationale": risk_rationale,
        "remediation_summary": remediation_summary,
        "alert_type": req.alert_type,
        "alert_fingerprint": req.alert_fingerprint,
    }
