"""Firestore Admin-SDK persistence layer -- the SOLE enforcement point.

The Firebase Admin SDK BYPASSES ``firestore.rules`` entirely (documented
privileged access; verified July 2026). So every invariant that the rules would
have protected against a client is RE-ENFORCED here in code. Each enforcement
point is annotated with the invariant number from the contract:

  1. Approvals are BORN 'pending'; create rejects any pre-set decision field,
     non-pending status, OR unknown key (hasOnly bound).   -> ``create_approval``
  2. Only pending -> approved|denied; re-deciding is 409.   -> ``decide``
  3. On decide ONLY the 5 decision keys change; all else frozen. -> ``decide``
  4. ``audit_log`` is APPEND-ONLY: never update/delete a row. (No update/delete
     method exists in this module.)
  5. Audit ``actor`` is ALWAYS the authenticated caller, never a body field.
     ``actor`` is a required *argument* to the decide/create calls, sourced by
     ``main.py`` from the verified principal.
  6. Status flip + audit row commit in ONE transaction.    -> ``decide``
  7. The n8n map is NEVER returned.                         -> ``_public_view``
  8. Inputs validated by pydantic upstream; this layer additionally re-checks
     the born-pending + hasOnly-key contract as defense in depth.

Emulator note: importing this module sets ``FIRESTORE_EMULATOR_HOST`` (if the
setting is present) BEFORE the client is built, which is the ordering the SDK
requires to swap in anonymous local credentials.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from typing import Any, Optional

# --- Emulator env ordering ------------------------------------------------- #
# Must run BEFORE firestore.client() is created. We read our own settings (which
# read the env) and, if an emulator host is configured, ensure the canonical
# env var the SDK looks for is populated. Idempotent and scheme-free.
from .config import get_settings  # noqa: E402

_settings = get_settings()
if _settings.emulator_host:
    os.environ["FIRESTORE_EMULATOR_HOST"] = _settings.emulator_host  # host:port, no http://

import threading

import firebase_admin  # noqa: E402
from firebase_admin import firestore  # noqa: E402

_app_lock = threading.Lock()

from .models import (  # noqa: E402
    ApprovalPublic,
    CreateApprovalRequest,
    Decision,
    DecisionChannel,
    Status,
)
from .ulid import new_ulid  # noqa: E402

# --------------------------------------------------------------------------- #
# Errors surfaced to main.py -> mapped to HTTP status codes there.
# --------------------------------------------------------------------------- #
class NotFoundError(Exception):
    """Requested approval does not exist -> 404."""


class ConflictError(Exception):
    """Approval is not 'pending' (already decided/other state) -> 409."""


class InvariantViolation(Exception):
    """A payload violated the born-pending / key-set / freeze contract -> 400."""


# The exact set of keys a decision may change. Mirrors the ``changedKeys()``
# allowlist in firestore.rules (invariant 3). The decide write set MUST be a
# subset of this; anything outside it is a frozen field and may not be written.
_DECISION_MUTABLE_KEYS = frozenset(
    {"status", "decided_by", "decided_at", "decision_channel", "decision_note"}
)

# Decision fields that must NOT be present at create time (invariant 1).
_FORBIDDEN_ON_CREATE = ("decided_at", "decided_by", "decision_channel", "decision_note")

# The COMPLETE set of keys a create payload may carry -- mirrors the rules'
# keys().hasOnly([...]) bound (firestore.rules, create contract). Any key outside
# this set is rejected at the repo layer too, so the layer is genuinely safe
# against a hand-built payload that bypasses pydantic (invariant 1 + 8).
_ALLOWED_CREATE_KEYS = frozenset(
    {
        "plan_format",
        "plan_summary",
        "plan_inline",
        "plan_ref",
        "plan_hash",
        "risk",
        "risk_rationale",
        "remediation_summary",
        "alert_type",
        "alert_payload",
        "alert_fingerprint",
        "incident_id",
        "n8n",
        "expires_at",
    }
)


# --------------------------------------------------------------------------- #
# App / client bootstrap
# --------------------------------------------------------------------------- #
def _ensure_app() -> None:
    """Initialize the default firebase_admin app exactly once (production path)."""
    if not firebase_admin._apps:
        with _app_lock:
            if not firebase_admin._apps:
                if _settings.credentials_path:
                    cred = firebase_admin.credentials.Certificate(_settings.credentials_path)
                    firebase_admin.initialize_app(cred, options={"projectId": _settings.project_id})
                else:
                    firebase_admin.initialize_app(options={"projectId": _settings.project_id})


_db_client = None


def get_db():
    """Return a cached Firestore client.

    Emulator: build a google-cloud-firestore Client with AnonymousCredentials.
    firebase_admin's firestore.client() resolves Application Default Credentials
    even when FIRESTORE_EMULATOR_HOST is set, which fails on any box without a
    service account (CI, a teammate laptop). google.cloud.firestore.Client honors
    the emulator env var and is the exact type the Admin SDK returns, so every
    downstream call (.collection/.document/.transaction, @firestore.transactional)
    is identical. Production keeps the Admin SDK client.
    """
    global _db_client
    if _db_client is not None:
        return _db_client
    if _settings.emulator_host:
        from google.auth.credentials import AnonymousCredentials
        from google.cloud import firestore as gcf

        _db_client = gcf.Client(project=_settings.project_id, credentials=AnonymousCredentials())
    else:
        _ensure_app()
        _db_client = firestore.client()
    return _db_client


# --------------------------------------------------------------------------- #
# Serialization helpers
# --------------------------------------------------------------------------- #
def _iso(value: Any) -> Any:
    """Coerce Firestore timestamp/datetime values to ISO-8601 strings."""
    if isinstance(value, _dt.datetime):
        return value.isoformat()
    # google's DatetimeWithNanoseconds subclasses datetime, so the above covers
    # it; anything else passes through untouched.
    return value


def _public_view(data: dict[str, Any]) -> ApprovalPublic:
    """Build the client-safe view of an approval.

    INVARIANT 7: the ``n8n`` map is a bearer capability and is stripped here --
    this is the single choke point every read path funnels through, so the
    resume URL can never leak into a response.
    """
    safe = dict(data)
    safe.pop("n8n", None)  # <-- the capability strip (invariant 7)
    for ts_field in ("created_at", "expires_at", "decided_at"):
        if ts_field in safe:
            safe[ts_field] = _iso(safe[ts_field])
    return ApprovalPublic.model_validate(safe)


def get_n8n_handle(data: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Return the raw ``n8n`` map for SERVER-INTERNAL use (the resume POST).

    This is deliberately separate from ``_public_view`` and is only ever called
    by the decide/resume flow to fire the resume webhook -- it is NEVER part of a
    response body. Tolerates ``None`` (a caller that lost the doc) so it can
    never raise on a missing input.
    """
    if not isinstance(data, dict):
        return None
    n8n = data.get("n8n")
    return dict(n8n) if isinstance(n8n, dict) else None


# --------------------------------------------------------------------------- #
# Audit log (append-only)
# --------------------------------------------------------------------------- #
def _build_audit_row(
    *,
    event_type: str,
    actor: str,
    channel: Optional[str],
    approval_ref: Optional[str],
    incident_id: Optional[str],
    before: Optional[dict[str, Any]],
    after: Optional[dict[str, Any]],
    detail: Optional[str],
    source_ip: Optional[str],
    event_id: str,
) -> dict[str, Any]:
    """Construct an audit row for a pre-generated ULID doc id.

    INVARIANT 5: ``actor`` is passed in from the authenticated caller. There is
    intentionally no code path that derives ``actor`` from a request body.
    ``timestamp`` is SERVER_TIMESTAMP (server-set, not client-asserted).
    """
    return {
        "event_id": event_id,
        "event_type": event_type,
        "approval_ref": approval_ref,
        "incident_id": incident_id,
        "actor": actor,  # server-set (invariant 5)
        "channel": channel,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "before": before,
        "after": after,
        "detail": detail,
        "source_ip": source_ip,
        "prev_hash": None,  # hash-chain population is a Week-5+ enhancement
        "entry_hash": None,
        "schema_version": _settings.schema_version,
    }


# --------------------------------------------------------------------------- #
# CREATE  -- POST /approvals
# --------------------------------------------------------------------------- #
def create_approval(req: CreateApprovalRequest, *, actor: str, source_ip: Optional[str] = None) -> dict[str, Any]:
    """Create ONE pending approval doc + its ``approval_created`` audit row.

    Both writes go through a single transaction so there is never an approval
    without its creation audit trail (mirrors the decide atomicity guarantee).

    Returns the raw stored dict (caller wraps in ``_public_view``).
    """
    db = get_db()

    # --- INVARIANT 1 + 8 (defense in depth): the pydantic model already forbids
    # decision keys / unknown keys / a ``status`` field, but re-assert here so
    # this layer is safe even if called with a hand-built payload in a test. ----
    payload = req.model_dump(exclude_none=False)

    # (a) hasOnly key bound -- mirror the rules; reject any unexpected key.
    unknown = set(payload) - _ALLOWED_CREATE_KEYS
    if unknown:
        raise InvariantViolation(f"unknown key(s) on create: {sorted(unknown)}")

    # (b) no decision field pre-set.
    for forbidden in _FORBIDDEN_ON_CREATE:
        if payload.get(forbidden) is not None:
            raise InvariantViolation(f"decision field '{forbidden}' must not be set on create")

    # (c) no pre-set / non-pending status.
    if payload.get("status") not in (None, Status.pending.value):
        raise InvariantViolation("approvals are born 'pending'; status may not be pre-set")

    # (d) inline-plan size guard (SCHEMA.md: < ~200KB).
    if payload.get("plan_inline") is not None:
        if len(payload["plan_inline"].encode("utf-8")) > _settings.max_plan_inline_bytes:
            raise InvariantViolation("plan_inline exceeds inline size cap; use plan_ref instead")

    # (e) alert_payload size guard -- the map is attacker-influenced and unbounded
    # in the model; cap it so it cannot inflate the doc toward the 1MiB limit.
    payload_bytes = len(json.dumps(payload["alert_payload"], default=str).encode("utf-8"))
    if payload_bytes > _settings.max_alert_payload_bytes:
        raise InvariantViolation("alert_payload exceeds size cap")

    # Generate the id BEFORE writing so it can be embedded in resume flows.
    approval_id = new_ulid(prefix="apr_")
    approval_ref = db.collection(_settings.approvals_collection).document(approval_id)

    # Full doc, snake_case, server-controlled fields forced by us (not the body).
    doc = {
        "approval_id": approval_id,
        "status": Status.pending.value,  # BORN pending (invariant 1)
        "plan_format": payload["plan_format"],
        "plan_summary": payload["plan_summary"],
        "plan_inline": payload.get("plan_inline"),
        "plan_ref": payload.get("plan_ref"),
        "plan_hash": payload["plan_hash"],
        "risk": payload["risk"],
        "risk_rationale": payload.get("risk_rationale"),
        "remediation_summary": payload.get("remediation_summary"),
        "alert_type": payload["alert_type"],
        "alert_payload": payload["alert_payload"],
        "alert_fingerprint": payload.get("alert_fingerprint"),
        "incident_id": payload["incident_id"],
        "n8n": payload["n8n"],  # bearer capability -- stored, never returned
        "created_at": firestore.SERVER_TIMESTAMP,  # server-set (invariant 1)
        "expires_at": payload.get("expires_at"),
        # Decision fields explicitly born null.
        "decided_at": None,
        "decided_by": None,
        "decision_channel": None,
        "decision_note": None,
        "schema_version": _settings.schema_version,
    }

    # NOTE: audit_id is generated ONCE, OUTSIDE the @transactional retry loop, ON
    # PURPOSE. On a contention retry, txn.set(audit_ref, ...) overwrites the same
    # doc id (idempotent) rather than appending a duplicate audit row. Do NOT
    # move this generation inside the transactional function.
    audit_id = new_ulid(prefix="evt_")
    audit_row = _build_audit_row(
        event_type="approval_created",
        actor=actor,  # invariant 5
        channel="api",
        approval_ref=approval_id,
        incident_id=payload["incident_id"],
        before=None,
        after={"status": Status.pending.value},
        detail=f"Approval gate created for alert_type={payload['alert_type']}",
        source_ip=source_ip,
        event_id=audit_id,
    )
    audit_ref = db.collection(_settings.audit_collection).document(audit_id)

    transaction = db.transaction()

    @firestore.transactional
    def _create(txn):
        # Pure writes (no prior read needed); still transactional so the approval
        # and its creation-audit row commit together.
        txn.set(approval_ref, doc)
        txn.set(audit_ref, audit_row)

    _create(transaction)

    # Read back so timestamps are resolved for the response.
    return approval_ref.get().to_dict()


# --------------------------------------------------------------------------- #
# READ  -- GET /approvals/{id} and GET /approvals/pending
# --------------------------------------------------------------------------- #
def get_approval_public(approval_id: str) -> ApprovalPublic:
    """Return one approval with the n8n map stripped, or raise NotFoundError."""
    snap = get_db().collection(_settings.approvals_collection).document(approval_id).get()
    if not snap.exists:
        raise NotFoundError(approval_id)
    return _public_view(snap.to_dict())  # invariant 7


def get_approval_raw(approval_id: str) -> dict[str, Any]:
    """Return the RAW approval dict (n8n map intact) for server-internal use.

    Used only by the resume-recovery path in ``main.py``; never returned to a
    client. Raises NotFoundError if the approval is gone.
    """
    snap = get_db().collection(_settings.approvals_collection).document(approval_id).get()
    if not snap.exists:
        raise NotFoundError(approval_id)
    return snap.to_dict()


def list_pending_public(limit: Optional[int] = None) -> list[ApprovalPublic]:
    """List pending approvals (oldest first), n8n map stripped from each.

    Query mirrors SCHEMA.md: ``where(status==pending).orderBy(created_at ASC)``.
    The composite index is declared in firestore.indexes.json (prod); the
    emulator auto-indexes.
    """
    q = (
        get_db()
        .collection(_settings.approvals_collection)
        .where(filter=firestore.FieldFilter("status", "==", Status.pending.value))
        .order_by("created_at", direction=firestore.Query.ASCENDING)
    )
    if limit is not None:
        q = q.limit(limit)
    return [_public_view(doc.to_dict()) for doc in q.stream()]  # invariant 7


def list_recent_public(limit: Optional[int] = None) -> list[ApprovalPublic]:
    """List DECIDED approvals (newest decision first), n8n map stripped.

    Feeds the Web UI History tab. ``decided_at`` is null while pending and a
    server timestamp once decided, so a range filter on it excludes pending rows
    with a single-field index (a ``!= null`` filter is unsupported in Firestore).
    Passively-expired approvals keep ``decided_at`` null and are intentionally
    absent here until an expiry sweep writes them.
    """
    epoch = _dt.datetime(1970, 1, 1, tzinfo=_dt.timezone.utc)
    q = (
        get_db()
        .collection(_settings.approvals_collection)
        .where(filter=firestore.FieldFilter("decided_at", ">", epoch))
        .order_by("decided_at", direction=firestore.Query.DESCENDING)
    )
    if limit is not None:
        q = q.limit(limit)
    return [_public_view(doc.to_dict()) for doc in q.stream()]  # invariant 7


# --------------------------------------------------------------------------- #
# DECIDE  -- POST /approvals/{id}/decide (the critical transaction)
# --------------------------------------------------------------------------- #
def decide(
    approval_id: str,
    *,
    decision: Decision,
    actor: str,
    channel: DecisionChannel,
    note: Optional[str],
    source_ip: Optional[str] = None,
) -> dict[str, Any]:
    """Record a decision transactionally + append its audit row atomically.

    INVARIANTS enforced here:
      2. pending-only: read the doc inside the txn; 404 if absent, 409 if
         status != 'pending'. This blocks a Web-UI double-click racing a Slack
         action -- only one can flip 'pending' and resume n8n.
      3. changed-key allowlist: the write set is a fixed dict of ONLY the 5
         permitted keys, and we assert that write-set's keys are a subset of the
         allowlist BEFORE writing. Because we use ``txn.update()`` with that
         exact dict, every plan_*/alert_*/risk*/n8n/created_at/incident_id/
         approval_id/expires_at/schema_version field is physically untouched.
      6. atomicity: the status flip and the audit append are both ``txn`` writes
         -> one commit. There can be no decided approval without its audit row.
      5. actor is the passed-in authenticated principal.

    Returns the authoritative post-decision dict (built inside the txn, n8n map
    intact for the internal resume; caller wraps in ``_public_view``).
    """
    db = get_db()
    approval_ref = db.collection(_settings.approvals_collection).document(approval_id)

    # Defensive coercion: over HTTP ``channel`` is always a DecisionChannel, but a
    # hand-built/test caller could pass a raw string. Force it through the enum so
    # an out-of-enum channel token can never be persisted (parity with the
    # "safe against hand-built payloads" standard applied on create).
    if not isinstance(channel, DecisionChannel):
        try:
            channel = DecisionChannel(channel)
        except ValueError as exc:
            raise InvariantViolation(f"invalid decision_channel: {channel!r}") from exc

    new_status = Status.approved.value if decision is Decision.approve else Status.denied.value
    event_type = "approval_approved" if decision is Decision.approve else "approval_denied"

    # NOTE: audit_id is generated ONCE, OUTSIDE the @transactional retry loop, ON
    # PURPOSE. On a contention retry, txn.set(audit_ref, ...) overwrites the same
    # doc id (idempotent) rather than appending a duplicate audit row. Do NOT
    # move this generation inside _decide().
    audit_id = new_ulid(prefix="evt_")
    audit_ref = db.collection(_settings.audit_collection).document(audit_id)

    transaction = db.transaction()

    @firestore.transactional
    def _decide(txn) -> dict[str, Any]:
        # ---- ALL READS FIRST (Firestore txn rule) -------------------------- #
        snap = approval_ref.get(transaction=txn)
        if not snap.exists:
            raise NotFoundError(approval_id)  # invariant 2 -> 404
        current = snap.to_dict()

        # ---- INVARIANT 2: pending-only transition (idempotency) ------------ #
        if current.get("status") != Status.pending.value:
            raise ConflictError(
                f"approval {approval_id} is '{current.get('status')}', not 'pending'"
            )

        # ---- The write set: EXACTLY the 5 decision keys, nothing else ------ #
        updates = {
            "status": new_status,
            "decided_at": firestore.SERVER_TIMESTAMP,
            "decided_by": actor,  # invariant 5 (authenticated principal)
            "decision_channel": channel.value,
            "decision_note": note,
        }

        # ---- INVARIANT 3: assert the WRITE SET touches only allowlisted keys #
        # This constrains the actual bytes written. Unlike a diff of a copied
        # doc (which can never differ outside the allowlist), this stays true and
        # will FAIL LOUDLY if someone ever adds a frozen field to ``updates``.
        illegal = set(updates) - _DECISION_MUTABLE_KEYS
        if illegal:
            raise InvariantViolation(
                f"decide would mutate frozen field(s): {sorted(illegal)}"
            )

        # ---- The write: update() with ONLY the decision fields (not set()) -- #
        # update() with this fixed dict leaves every frozen field physically
        # untouched -- belt-and-suspenders with the assertion above.
        txn.update(approval_ref, updates)

        # ---- INVARIANT 6: audit row in the SAME transaction ---------------- #
        # ``before`` is DERIVED from the doc actually read in this txn, not
        # hardcoded, so it stays correct if the pending-only precondition is ever
        # relaxed.
        audit_row = _build_audit_row(
            event_type=event_type,
            actor=actor,  # invariant 5
            channel=channel.value,
            approval_ref=approval_id,
            incident_id=current.get("incident_id"),
            before={"status": current.get("status")},
            after={"status": new_status},
            detail=note,
            source_ip=source_ip,
            event_id=audit_id,
        )
        txn.set(audit_ref, audit_row)

        # ---- Build the AUTHORITATIVE post-write projection to return -------- #
        # We drive the response AND the internal resume off this in-transaction
        # value -- never a second, unsynchronized get() that could observe a
        # deletion (500) or an interleaved write. ``decided_at`` is shown as a
        # local now(); the durable value is the server timestamp just written.
        result = dict(current)
        result.update(updates)
        result["decided_at"] = _dt.datetime.now(_dt.timezone.utc)
        return result

    stored = _decide(transaction)

    # Optional refinement: re-read to resolve the exact server timestamps for the
    # response. This is best-effort ONLY -- if the doc vanished in the post-commit
    # window we fall back to the authoritative in-txn projection rather than
    # crashing on ``None`` after a durable commit.
    try:
        snap = approval_ref.get()
        if snap.exists:
            return snap.to_dict()
    except Exception:  # noqa: BLE001 -- read-back is best-effort; never fatal
        pass
    return stored
