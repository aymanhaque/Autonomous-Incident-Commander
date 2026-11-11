"""Mock execution service (thin, stateless).

Stands in for Ayman's real execution API. Accepts a plan and pretends to apply /
roll back a Terraform change. Stateless -- no persistence, deterministic replies.

Run:  uvicorn mock_execution:app --port 8000
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

app = FastAPI(title="AIC Mock Execution", version="0.1.0")


class ApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_inline: Optional[str] = None
    plan_ref: Optional[str] = None
    incident_id: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _one_plan_source(self):
        # Must supply exactly one of plan_inline / plan_ref -- mirrors how the
        # real executor decides where to read the plan from.
        if bool(self.plan_inline) == bool(self.plan_ref):
            raise ValueError("provide exactly one of plan_inline or plan_ref")
        return self


class RollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_id: str = Field(..., min_length=1)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/apply")
def apply(req: ApplyRequest):
    # A real executor would run `terraform apply`; here we just ack. Validation
    # (exactly-one plan source) already ran during request parsing.
    return {"status": "applied", "incident_id": req.incident_id}


@app.post("/rollback")
def rollback(req: RollbackRequest):
    return {"status": "rolled_back", "incident_id": req.incident_id}
