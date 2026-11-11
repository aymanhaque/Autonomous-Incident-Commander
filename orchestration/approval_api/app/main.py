"""FastAPI app: the Generic Approval API (human-in-the-loop gate).

Routes:
  POST /approvals               -- n8n creates a pending gate
  GET  /approvals/pending       -- Route A / Web UI lists pending (n8n stripped)
  GET  /approvals/{id}          -- fetch one (n8n stripped)
  POST /approvals/{id}/decide   -- Route A or B records a decision, resumes n8n
  POST /approvals/{id}/resume   -- idempotent re-resume of an already-decided gate
  GET  /health                  -- liveness

TRUST BOUNDARY (documented, enforced):
  * The write endpoints (create / decide / resume) are gated by a SERVICE TOKEN
    (``Authorization: Bearer <API_SERVICE_TOKEN>``) that is the API's own
    authentication. In a non-emulator deployment with no token configured the
    API FAILS CLOSED (503) so a prod deploy can never accidentally run open.
  * The DECIDER identity (``decided_by`` and the audit ``actor``) is taken from
    the authenticated principal -- the ``X-Actor`` header in dev -- NOT from the
    request body. In production a gateway/JWT middleware verifies the caller and
    sets this header; the body has no field to supply an identity (invariant 5).
"""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request

from .config import get_settings
from .models import (
    CreateApprovalRequest,
    CreateApprovalResponse,
    Decision,
    DecideRequest,
    DecideResponse,
    DecisionChannel,
    PendingListResponse,
    RecentListResponse,
    ResumeResponse,
    Status,
)
from . import firestore_repo as repo
from .n8n_resume import resume_n8n

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aic.approval_api")

settings = get_settings()
app = FastAPI(title="AIC Generic Approval API", version="0.1.0")

# --------------------------------------------------------------------------- #
# CORS -- least-privilege, opt-in. No middleware at all unless explicit origins
# are configured (the safe default). We NEVER wildcard with credentials.
# --------------------------------------------------------------------------- #
if settings.cors_allow_origins:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "X-Actor"],
    )


# --------------------------------------------------------------------------- #
# Auth / trust boundary helpers
# --------------------------------------------------------------------------- #
def require_service_auth(
    authorization: Annotated[Optional[str], Header()] = None,
) -> None:
    """Gate the write endpoints with the shared service token.

    Fails CLOSED: if no token is configured and we are NOT talking to the
    emulator, refuse the request (503) rather than run open in prod. In the
    emulator/dev path a missing token is allowed so local runs stay frictionless.
    """
    if settings.service_token is None:
        if not settings.using_emulator:
            raise HTTPException(
                status_code=503,
                detail="API_SERVICE_TOKEN unset in non-emulator mode (fail-closed)",
            )
        return  # dev / emulator only
    if authorization != f"Bearer {settings.service_token}":
        raise HTTPException(status_code=401, detail="invalid or missing service token")


def _principal(x_actor: Optional[str]) -> str:
    """Resolve the authenticated principal from the X-Actor header.

    Dev behavior: read the header, fall back to a configured placeholder. In
    prod this is where a verified JWT subject/service identity is injected. The
    body is NEVER consulted for identity (invariant 5).
    """
    return x_actor if x_actor else settings.actor_fallback


def _client_ip(request: Request) -> Optional[str]:
    """Best-effort server-observed source IP for the audit row (not client-asserted)."""
    return request.client.host if request.client else None


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    return {"status": "ok", "using_emulator": settings.using_emulator}


@app.post(
    "/approvals",
    response_model=CreateApprovalResponse,
    status_code=201,
    dependencies=[Depends(require_service_auth)],
)
def create_approval(
    payload: CreateApprovalRequest,
    request: Request,
    x_actor: Annotated[Optional[str], Header()] = None,
):
    """n8n creates the gate. Returns only {approval_id, status} -- never the n8n map."""
    actor = _principal(x_actor)
    try:
        stored = repo.create_approval(payload, actor=actor, source_ip=_client_ip(request))
    except repo.InvariantViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return CreateApprovalResponse(approval_id=stored["approval_id"], status=stored["status"])


@app.get("/approvals/pending", response_model=PendingListResponse)
def list_pending(limit: Annotated[Optional[int], Query(ge=1, le=500)] = None):
    """Route A / Web UI: pending approvals oldest-first, n8n map stripped."""
    items = repo.list_pending_public(limit=limit)
    return PendingListResponse(items=items, count=len(items))


@app.get("/approvals/recent", response_model=RecentListResponse)
def list_recent(limit: Annotated[int, Query(ge=1, le=500)] = 50):
    """History tab feed: decided approvals, newest decision first, n8n stripped.

    Declared BEFORE ``/approvals/{approval_id}`` so the literal path wins route
    matching (FastAPI matches in declaration order).
    """
    items = repo.list_recent_public(limit=limit)
    return RecentListResponse(items=items, count=len(items))


@app.get("/approvals/{approval_id}", response_model=repo.ApprovalPublic)
def get_approval(approval_id: str):
    """Fetch one approval with the n8n map stripped. 404 if missing."""
    try:
        return repo.get_approval_public(approval_id)
    except repo.NotFoundError:
        raise HTTPException(status_code=404, detail="Approval not found")


@app.post(
    "/approvals/{approval_id}/decide",
    response_model=DecideResponse,
    dependencies=[Depends(require_service_auth)],
)
async def decide(
    approval_id: str,
    body: DecideRequest,
    request: Request,
    x_actor: Annotated[Optional[str], Header()] = None,
):
    """Record a decision transactionally, then resume the paused n8n workflow.

    Ordering matters: the decision + audit row commit FIRST (one transaction);
    only AFTER commit do we POST the resume URL. A resume failure yields a
    success-with-warning -- the durable decision is not corrupted. If the resume
    genuinely failed, ``POST /approvals/{id}/resume`` re-drives it idempotently.
    """
    actor = _principal(x_actor)  # invariant 5: identity from header, not body
    # Default channel 'api' unless the caller (a trusted server-side integration)
    # specified one. Route A (Web UI) sends 'web'; Route B sends slack/etc.
    channel = body.decision_channel or DecisionChannel.api

    # 1) Durable, atomic decision + audit write.
    try:
        stored = repo.decide(
            approval_id,
            decision=body.decision,
            actor=actor,
            channel=channel,
            note=body.decision_note,
            source_ip=_client_ip(request),
        )
    except repo.NotFoundError:
        raise HTTPException(status_code=404, detail="Approval not found")
    except repo.ConflictError as exc:
        # Already decided (or non-pending) -> 409, idempotency guard (invariant 2).
        raise HTTPException(status_code=409, detail=str(exc))
    except repo.InvariantViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 2) Fire-once resume to n8n using the INTERNAL n8n handle (never returned).
    n8n_handle = repo.get_n8n_handle(stored)
    resume_warning = None
    if n8n_handle:
        resume_warning = await resume_n8n(
            n8n_handle,
            approval_id=approval_id,
            decision=body.decision.value,
            decided_by=actor,
        )

    # 3) Respond with the n8n-stripped view (invariant 7) + any warning.
    return DecideResponse(approval=repo._public_view(stored), resume_warning=resume_warning)


@app.post(
    "/approvals/{approval_id}/resume",
    response_model=ResumeResponse,
    dependencies=[Depends(require_service_auth)],
)
async def re_resume(approval_id: str):
    """Idempotently re-drive the n8n resume for an ALREADY-decided approval.

    Recovery path for the case where the decision committed but the resume POST
    genuinely failed (a warning was returned, or the client never saw the
    response). It NEVER touches status/decision fields -- it only re-POSTs the
    resume URL -- so it is safe to call repeatedly. The n8n resume webhook is
    itself single-use per execution, so a late re-drive after a real success is
    a no-op on n8n's side (it will 404 the not-waiting execution, surfaced as a
    warning here). Requires the approval to be in a terminal decision state.
    """
    try:
        data = repo.get_approval_raw(approval_id)
    except repo.NotFoundError:
        raise HTTPException(status_code=404, detail="Approval not found")

    if data.get("status") not in (Status.approved.value, Status.denied.value):
        raise HTTPException(status_code=409, detail="approval is not in a decided state")

    n8n_handle = repo.get_n8n_handle(data)
    if not n8n_handle:
        raise HTTPException(status_code=422, detail="approval has no n8n resume handle")

    # Translate the stored Status back to the Decision token the workflow expects.
    # The Wait node's IF compares against 'approve'/'deny' (Decision), NOT the
    # stored 'approved'/'denied' (Status) -- sending the Status would route a
    # re-resumed APPROVED gate down the deny/abort branch and silently drop the
    # remediation. This mirrors the /decide path (body.decision.value).
    resume_decision = (
        Decision.approve.value
        if data["status"] == Status.approved.value
        else Decision.deny.value
    )
    warning = await resume_n8n(
        n8n_handle,
        approval_id=approval_id,
        decision=resume_decision,
        decided_by=data.get("decided_by") or settings.actor_fallback,
    )
    return ResumeResponse(approval_id=approval_id, resume_warning=warning)
