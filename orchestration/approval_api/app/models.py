"""Pydantic v2 request/response models for the Approval API.

Design rules baked into these models (mirroring ``firestore.rules`` +
``SCHEMA.md``):

* Create input REJECTS unknown/extra keys (``extra='forbid'``) so an attacker
  cannot smuggle ``decided_*``/``decision_*`` or an ``n8n`` override in through a
  typo'd or undocumented field. (Pydantic's default is ``ignore`` which SILENTLY
  drops extras -- not acceptable here.)
* Create input has NO decision fields and NO ``status`` field at all: approvals
  are BORN 'pending' (invariant 1). The server sets ``status='pending'`` and
  ``created_at`` itself.
* The response models NEVER contain the ``n8n`` map (invariant 7). There is no
  field for it, so it cannot be serialized out even by accident.
* The n8n ``resume_webhook_url`` is a caller-supplied capability that the server
  later POSTs to; it is validated here against a scheme + host allowlist so it
  cannot become an SSRF primitive (metadata endpoints, internal services, etc.).
"""

from __future__ import annotations

import enum
import ipaddress
import socket
from typing import Any, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import get_settings


# --------------------------------------------------------------------------- #
# Enums (string-valued so they serialize as the SCHEMA.md snake_case tokens)
# --------------------------------------------------------------------------- #
class Status(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    denied = "denied"
    expired = "expired"
    executing = "executing"
    executed = "executed"
    rolled_back = "rolled_back"
    failed = "failed"


class Risk(str, enum.Enum):
    Low = "Low"
    Med = "Med"
    High = "High"


class DecisionChannel(str, enum.Enum):
    web = "web"
    curl = "curl"
    slack = "slack"
    teams = "teams"
    pagerduty = "pagerduty"
    api = "api"


class Decision(str, enum.Enum):
    approve = "approve"
    deny = "deny"


# --------------------------------------------------------------------------- #
# n8n resume handle (accepted on CREATE, never returned)
# --------------------------------------------------------------------------- #
class N8nHandle(BaseModel):
    """The n8n resume capability. Persisted on the approval doc, NEVER returned.

    ``resume_webhook_url`` is a bearer token: POSTing to it resumes the paused
    remediation workflow. It is validated on the way in (scheme + host allowlist
    + method allowlist to defeat SSRF) but stripped from every outbound response
    by ``firestore_repo._public_view``.
    """

    model_config = ConfigDict(extra="forbid")

    execution_id: str = Field(..., min_length=1)
    resume_webhook_url: str = Field(..., min_length=1)
    # Default POST per n8n Wait-node contract; caller may pin another method.
    resume_method: str = Field(default="POST", min_length=1)
    workflow_id: str = Field(..., min_length=1)

    @field_validator("resume_webhook_url")
    @classmethod
    def _safe_url(cls, value: str) -> str:
        """Reject any resume URL that could be turned into an SSRF request.

        The URL is later POSTed server-side, so we constrain it HARD:
          * scheme must be http/https (no file://, gopher://, etc.);
          * host must be in ``N8N_RESUME_ALLOWED_HOSTS``;
          * if the host resolves to a link-local address (e.g. the
            169.254.169.254 metadata endpoint), it is blocked even if it slipped
            past the name allowlist.
        """
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("resume_webhook_url must use http or https")
        host = parsed.hostname or ""
        if not host:
            raise ValueError("resume_webhook_url must include a host")

        allowed = get_settings().n8n_resume_allowed_hosts
        if host not in allowed:
            raise ValueError(
                f"resume_webhook_url host '{host}' is not in N8N_RESUME_ALLOWED_HOSTS"
            )

        # Belt-and-suspenders: block link-local / metadata targets even when the
        # host name is allowlisted (defends against a poisoned allowlist entry or
        # a name that resolves somewhere hostile). Loopback is permitted only if
        # it was explicitly allowlisted (localhost/127.0.0.1 are common dev hosts).
        try:
            for info in socket.getaddrinfo(host, None):
                ip = ipaddress.ip_address(info[4][0])
                if ip.is_link_local:
                    raise ValueError("resume_webhook_url resolves to a blocked address")
        except socket.gaierror:
            # Name does not resolve in this environment (e.g. the compose service
            # name on a host-side test run). The name allowlist already gates it;
            # do not hard-fail on resolution.
            pass
        return value

    @field_validator("resume_method")
    @classmethod
    def _safe_method(cls, value: str) -> str:
        """Constrain the caller-supplied method to a small allowlist."""
        upper = value.upper()
        if upper not in get_settings().n8n_resume_allowed_methods:
            raise ValueError(
                "resume_method must be one of "
                f"{sorted(get_settings().n8n_resume_allowed_methods)}"
            )
        return upper


# --------------------------------------------------------------------------- #
# POST /approvals  -- create the gate
# --------------------------------------------------------------------------- #
class CreateApprovalRequest(BaseModel):
    """Body n8n sends to create a pending approval.

    Note what is ABSENT and cannot be supplied by the client:
      * ``status``      -> server forces 'pending'
      * ``approval_id`` -> server generates a ULID
      * ``created_at``  -> server sets SERVER_TIMESTAMP
      * ``decided_at`` / ``decided_by`` / ``decision_channel`` / ``decision_note``
        -> decision fields; presence is impossible because ``extra='forbid'``
           rejects any key not declared here (invariant 1 + 8).
    """

    model_config = ConfigDict(extra="forbid")

    plan_format: str = Field(..., min_length=1, description="e.g. 'hcl'")
    plan_summary: str = Field(..., min_length=1)
    plan_inline: Optional[str] = Field(default=None, description="full plan if small")
    plan_ref: Optional[str] = Field(default=None, description="GCS/Storage URI for large plans")
    plan_hash: str = Field(..., min_length=1, description="sha256 of the full plan")
    risk: Risk
    risk_rationale: Optional[str] = None
    # Gemini's plain-English explanation of what the alert means and what the
    # plan does (the Web UI's "Remediation Solution" section). Distinct from
    # risk_rationale, which is just the final risk verdict.
    remediation_summary: Optional[str] = None
    alert_type: str = Field(..., min_length=1)
    alert_payload: dict[str, Any]
    alert_fingerprint: Optional[str] = None
    incident_id: str = Field(..., min_length=1)
    n8n: Optional[N8nHandle] = None
    # Optional SLA deadline as an ISO-8601 string; server stores it verbatim.
    expires_at: Optional[str] = None


class CreateApprovalResponse(BaseModel):
    """Minimal create ack -- deliberately does NOT echo the n8n map."""

    approval_id: str
    status: Status


# --------------------------------------------------------------------------- #
# POST /approvals/{id}/decide
# --------------------------------------------------------------------------- #
class DecideRequest(BaseModel):
    """Body for a decision.

    IMPORTANT trust boundary: this body carries the *decision* but NOT the
    *decider*. ``decided_by`` / audit ``actor`` come from the authenticated
    principal (the ``X-Actor`` header in dev), never from this body -- there is
    no field here to supply an identity, by design (invariant 5).
    """

    model_config = ConfigDict(extra="forbid")

    decision: Decision
    decision_note: Optional[str] = None
    decision_channel: Optional[DecisionChannel] = None


# --------------------------------------------------------------------------- #
# Public approval view (n8n map ALWAYS stripped)
# --------------------------------------------------------------------------- #
class ApprovalPublic(BaseModel):
    """The approval as returned to any client. No ``n8n`` field exists here, so
    the resume capability can never be serialized out (invariant 7).

    ``extra='ignore'`` (the default) is used on purpose: Firestore timestamps
    come back as native datetimes and we coerce them to ISO strings before
    building this model, but staying lenient means a future additive schema
    field won't break reads. The n8n map is removed *upstream* in the repo, not
    relied upon to be dropped here.
    """

    approval_id: str
    status: Status
    plan_format: str
    plan_summary: str
    plan_inline: Optional[str] = None
    plan_ref: Optional[str] = None
    plan_hash: str
    risk: Risk
    risk_rationale: Optional[str] = None
    remediation_summary: Optional[str] = None
    alert_type: str
    alert_payload: dict[str, Any] = Field(default_factory=dict)
    alert_fingerprint: Optional[str] = None
    incident_id: str
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None
    decision_channel: Optional[DecisionChannel] = None
    decision_note: Optional[str] = None
    schema_version: int = 1


class PendingListResponse(BaseModel):
    items: list[ApprovalPublic]
    count: int


class RecentListResponse(BaseModel):
    """Decided approvals, newest decision first -- feeds the History tab."""

    items: list[ApprovalPublic]
    count: int


class DecideResponse(BaseModel):
    """Decision result. ``resume_warning`` is non-null when the decision was
    durably recorded but the n8n resume POST failed (success-with-warning).
    """

    approval: ApprovalPublic
    resume_warning: Optional[str] = None


class ResumeResponse(BaseModel):
    """Result of an idempotent re-resume (recovery path for a missed resume)."""

    approval_id: str
    resume_warning: Optional[str] = None
