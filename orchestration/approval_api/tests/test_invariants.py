"""Invariant regression tests for the Generic Approval API (emulator-backed).

Each test maps to a numbered invariant from the contract. A regression that
weakens the code will fail exactly one of these. Run against a live emulator:

    export FIRESTORE_EMULATOR_HOST=127.0.0.1:8080
    export FIRESTORE_PROJECT_ID=aic-local
    pytest -q
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app import firestore_repo as repo
from app.models import (
    CreateApprovalRequest,
    Decision,
    DecisionChannel,
    N8nHandle,
    Risk,
    Status,
)


# --------------------------------------------------------------------------- #
# Invariant 1: approvals are BORN pending
# --------------------------------------------------------------------------- #
def test_created_approval_is_born_pending(sample_create):
    stored = repo.create_approval(sample_create(), actor="n8n-service")
    assert stored["status"] == Status.pending.value
    # Decision fields are born null.
    assert stored["decided_at"] is None
    assert stored["decided_by"] is None
    assert stored["decision_channel"] is None
    assert stored["decision_note"] is None
    # created_at was server-set (resolved to a real timestamp on read-back).
    assert stored["created_at"] is not None


# --------------------------------------------------------------------------- #
# Invariant 1 + 8: reject pre-set decision fields / unknown keys on create
# --------------------------------------------------------------------------- #
def test_create_rejects_preset_decision_fields_via_model():
    # Pydantic (extra='forbid') rejects any decision key on the create body.
    with pytest.raises(ValidationError):
        CreateApprovalRequest(
            plan_format="hcl",
            plan_summary="x",
            plan_hash="h",
            risk=Risk.Low,
            alert_type="504",
            alert_payload={},
            incident_id="inc",
            n8n=N8nHandle(
                execution_id="1",
                resume_webhook_url="http://n8n/webhook-waiting/1",
                workflow_id="wf",
            ),
            decided_by="attacker",  # <-- forbidden extra key
        )


def test_create_rejects_status_override_via_model():
    with pytest.raises(ValidationError):
        CreateApprovalRequest(
            plan_format="hcl",
            plan_summary="x",
            plan_hash="h",
            risk=Risk.Low,
            alert_type="504",
            alert_payload={},
            incident_id="inc",
            n8n=N8nHandle(
                execution_id="1",
                resume_webhook_url="http://n8n/webhook-waiting/1",
                workflow_id="wf",
            ),
            status="approved",  # <-- forbidden: status is server-controlled
        )


def test_repo_defense_in_depth_rejects_preset_decision_field(sample_create):
    # A hand-built request that smuggles a decision field past pydantic (by
    # forcing an undeclared instance attr that then dumps) must be caught at the
    # repo layer. We monkeypatch model_dump to simulate that hostile payload.
    req = sample_create()
    original = req.model_dump()

    def _hostile_dump(*args, **kwargs):
        d = dict(original)
        d["decided_by"] = "attacker"  # decision field smuggled in
        return d

    object.__setattr__(req, "model_dump", _hostile_dump)
    with pytest.raises(repo.InvariantViolation):
        repo.create_approval(req, actor="n8n-service")


def test_repo_defense_in_depth_rejects_unknown_key(sample_create):
    # The repo re-asserts the rules' hasOnly bound: an unknown key on a
    # hand-built payload is rejected even though it bypassed pydantic.
    req = sample_create()
    original = req.model_dump()

    def _hostile_dump(*args, **kwargs):
        d = dict(original)
        d["totally_unknown_field"] = "surprise"
        return d

    object.__setattr__(req, "model_dump", _hostile_dump)
    with pytest.raises(repo.InvariantViolation):
        repo.create_approval(req, actor="n8n-service")


# --------------------------------------------------------------------------- #
# SSRF guard: resume_webhook_url must be scheme+host allowlisted
# --------------------------------------------------------------------------- #
def test_n8n_url_rejects_metadata_endpoint():
    # 169.254.169.254 (metadata) is neither allowlisted nor allowed (link-local).
    with pytest.raises(ValidationError):
        N8nHandle(
            execution_id="1",
            resume_webhook_url="http://169.254.169.254/latest/meta-data/",
            workflow_id="wf",
        )


def test_n8n_url_rejects_disallowed_host():
    with pytest.raises(ValidationError):
        N8nHandle(
            execution_id="1",
            resume_webhook_url="http://evil.example.com/webhook-waiting/1",
            workflow_id="wf",
        )


def test_n8n_url_rejects_non_http_scheme():
    with pytest.raises(ValidationError):
        N8nHandle(
            execution_id="1",
            resume_webhook_url="file:///etc/passwd",
            workflow_id="wf",
        )


def test_n8n_method_allowlist():
    with pytest.raises(ValidationError):
        N8nHandle(
            execution_id="1",
            resume_webhook_url="http://n8n/webhook-waiting/1",
            resume_method="DELETE",
            workflow_id="wf",
        )


# --------------------------------------------------------------------------- #
# Invariant 2: only pending -> approved|denied; 409 on re-decide
# --------------------------------------------------------------------------- #
def test_pending_to_approved_transition(sample_create):
    stored = repo.create_approval(sample_create(), actor="n8n-service")
    result = repo.decide(
        stored["approval_id"],
        decision=Decision.approve,
        actor="tarik@securivai.example",
        channel=DecisionChannel.api,
        note="ok",
    )
    assert result["status"] == Status.approved.value


def test_redecide_is_conflict(sample_create):
    stored = repo.create_approval(sample_create(), actor="n8n-service")
    repo.decide(
        stored["approval_id"],
        decision=Decision.approve,
        actor="first",
        channel=DecisionChannel.web,
        note=None,
    )
    # A second decision (Web double-click / concurrent Slack) must 409.
    with pytest.raises(repo.ConflictError):
        repo.decide(
            stored["approval_id"],
            decision=Decision.deny,
            actor="second",
            channel=DecisionChannel.slack,
            note=None,
        )
    # And the first decision stands unchanged.
    final = repo.get_approval_public(stored["approval_id"])
    assert final.status == Status.approved
    assert final.decided_by == "first"


def test_decide_missing_is_not_found():
    with pytest.raises(repo.NotFoundError):
        repo.decide(
            "apr_DOESNOTEXIST",
            decision=Decision.approve,
            actor="x",
            channel=DecisionChannel.api,
            note=None,
        )


# --------------------------------------------------------------------------- #
# Invariant 3: only the 5 decision keys change; everything else frozen
# --------------------------------------------------------------------------- #
def test_decide_freezes_all_non_decision_fields(sample_create, db):
    stored = repo.create_approval(sample_create(), actor="n8n-service")
    approval_id = stored["approval_id"]
    before = db.collection("approvals").document(approval_id).get().to_dict()

    repo.decide(
        approval_id,
        decision=Decision.approve,
        actor="tarik",
        channel=DecisionChannel.curl,
        note="note",
    )
    after = db.collection("approvals").document(approval_id).get().to_dict()

    frozen = [
        "approval_id", "plan_format", "plan_summary", "plan_inline", "plan_ref",
        "plan_hash", "risk", "risk_rationale", "alert_type", "alert_payload",
        "alert_fingerprint", "incident_id", "n8n", "created_at", "expires_at",
        "schema_version",
    ]
    for field in frozen:
        assert before[field] == after[field], f"frozen field '{field}' changed on decide"

    # Only the decision fields moved.
    assert after["status"] == Status.approved.value
    assert after["decided_by"] == "tarik"
    assert after["decision_channel"] == DecisionChannel.curl.value
    assert after["decision_note"] == "note"
    assert after["decided_at"] is not None


def test_decide_channel_coercion_rejects_bad_string(sample_create):
    # A hand-built caller passing a raw out-of-enum channel string is rejected at
    # the repo boundary rather than persisting a bad token.
    stored = repo.create_approval(sample_create(), actor="n8n-service")
    with pytest.raises(repo.InvariantViolation):
        repo.decide(
            stored["approval_id"],
            decision=Decision.approve,
            actor="tarik",
            channel="not-a-real-channel",  # type: ignore[arg-type]
            note=None,
        )


# --------------------------------------------------------------------------- #
# Invariant 4 + 6: audit row written atomically with the status flip
# --------------------------------------------------------------------------- #
def test_decide_writes_exactly_one_audit_row_atomically(sample_create, db):
    stored = repo.create_approval(sample_create(), actor="n8n-service")
    approval_id = stored["approval_id"]

    # After create there is exactly one 'approval_created' row.
    created_rows = [
        d.to_dict() for d in db.collection("audit_log").stream()
        if d.to_dict().get("event_type") == "approval_created"
           and d.to_dict().get("approval_ref") == approval_id
    ]
    assert len(created_rows) == 1

    repo.decide(
        approval_id,
        decision=Decision.deny,
        actor="tarik",
        channel=DecisionChannel.web,
        note="nope",
    )

    decision_rows = [
        d.to_dict() for d in db.collection("audit_log").stream()
        if d.to_dict().get("event_type") == "approval_denied"
           and d.to_dict().get("approval_ref") == approval_id
    ]
    # Exactly one decision audit row -> status flip and audit committed together.
    assert len(decision_rows) == 1
    row = decision_rows[0]
    # 'before' is DERIVED from the doc read inside the txn, not hardcoded.
    assert row["before"] == {"status": "pending"}
    assert row["after"] == {"status": "denied"}
    assert row["timestamp"] is not None  # SERVER_TIMESTAMP resolved


# --------------------------------------------------------------------------- #
# Invariant 5: audit actor is the server-supplied principal, not a body field
# --------------------------------------------------------------------------- #
def test_audit_actor_is_server_principal_not_body(sample_create, db):
    stored = repo.create_approval(sample_create(), actor="n8n-service")
    approval_id = stored["approval_id"]

    # The DecideRequest body has no identity field at all (extra='forbid').
    from app.models import DecideRequest
    with pytest.raises(ValidationError):
        DecideRequest(decision="approve", actor="forged-identity")

    # The actor recorded is exactly what the caller passed (the authed principal).
    repo.decide(
        approval_id,
        decision=Decision.approve,
        actor="verified-principal@securivai.example",
        channel=DecisionChannel.api,
        note=None,
    )
    row = [
        d.to_dict() for d in db.collection("audit_log").stream()
        if d.to_dict().get("event_type") == "approval_approved"
    ][0]
    assert row["actor"] == "verified-principal@securivai.example"
    approval = db.collection("approvals").document(approval_id).get().to_dict()
    assert approval["decided_by"] == "verified-principal@securivai.example"


# --------------------------------------------------------------------------- #
# Invariant 7: the n8n map is NEVER in any response view
# --------------------------------------------------------------------------- #
def test_n8n_map_stripped_from_get(sample_create):
    stored = repo.create_approval(sample_create(), actor="n8n-service")
    public = repo.get_approval_public(stored["approval_id"])
    dumped = public.model_dump()
    assert "n8n" not in dumped
    # Sanity: the raw stored doc DID have the capability (proves it was stripped).
    assert stored["n8n"]["resume_webhook_url"].endswith("/31987")


def test_n8n_map_stripped_from_pending_list(sample_create):
    repo.create_approval(sample_create(), actor="n8n-service")
    repo.create_approval(sample_create(incident_id="inc_test_0002"), actor="n8n-service")
    items = repo.list_pending_public()
    assert len(items) == 2
    for item in items:
        assert "n8n" not in item.model_dump()


def test_public_view_helper_strips_n8n():
    view = repo._public_view(
        {
            "approval_id": "apr_x",
            "status": "pending",
            "plan_format": "hcl",
            "plan_summary": "s",
            "plan_hash": "h",
            "risk": "Low",
            "alert_type": "504",
            "alert_payload": {},
            "incident_id": "inc",
            "schema_version": 1,
            "n8n": {"resume_webhook_url": "http://secret/webhook-waiting/9"},
        }
    )
    assert "n8n" not in view.model_dump()


# --------------------------------------------------------------------------- #
# Invariant 4 (explicit): the API exposes no audit mutate/delete path
# --------------------------------------------------------------------------- #
def test_no_audit_mutation_api_exists():
    # The repo module intentionally has no function that updates or deletes an
    # audit row. This guards against a future refactor adding one.
    forbidden = [
        name for name in dir(repo)
        if ("audit" in name.lower()) and any(v in name.lower() for v in ("update", "delete", "mutate"))
    ]
    assert forbidden == [], f"audit_log must be append-only; found: {forbidden}"


# --------------------------------------------------------------------------- #
# GET /approvals/recent (History tab feed)
# --------------------------------------------------------------------------- #
def test_recent_lists_decided_newest_first(sample_create):
    from app.models import Decision, DecisionChannel

    first = repo.create_approval(sample_create(), actor="n8n")
    second = repo.create_approval(sample_create(incident_id="inc_test_0002"), actor="n8n")
    repo.decide(
        first["approval_id"],
        decision=Decision.approve,
        actor="alice",
        channel=DecisionChannel.api,
        note=None,
    )
    repo.decide(
        second["approval_id"],
        decision=Decision.deny,
        actor="bob",
        channel=DecisionChannel.api,
        note=None,
    )

    recent = repo.list_recent_public()
    ids = [item.approval_id for item in recent]
    assert ids == [second["approval_id"], first["approval_id"]]
    assert recent[0].status.value == "denied"
    assert recent[1].status.value == "approved"


def test_recent_excludes_pending_and_strips_n8n(sample_create):
    from app.models import Decision, DecisionChannel

    decided = repo.create_approval(sample_create(), actor="n8n")
    pending = repo.create_approval(sample_create(incident_id="inc_test_0003"), actor="n8n")
    repo.decide(
        decided["approval_id"],
        decision=Decision.approve,
        actor="alice",
        channel=DecisionChannel.api,
        note=None,
    )

    recent = repo.list_recent_public()
    ids = [item.approval_id for item in recent]
    assert decided["approval_id"] in ids
    assert pending["approval_id"] not in ids
    for item in recent:
        assert "n8n" not in item.model_dump()


def test_recent_respects_limit(sample_create):
    from app.models import Decision, DecisionChannel

    for i in range(3):
        doc = repo.create_approval(sample_create(incident_id=f"inc_lim_{i}"), actor="n8n")
        repo.decide(
            doc["approval_id"],
            decision=Decision.approve,
            actor="alice",
            channel=DecisionChannel.api,
            note=None,
        )
    assert len(repo.list_recent_public(limit=2)) == 2


# --------------------------------------------------------------------------- #
# /resume recovery must send the Decision token ('approve'), not Status ('approved')
# (regression: the n8n IF node compares against 'approve'; sending 'approved'
#  routed an approved re-resume to the abort branch and dropped the remediation)
# --------------------------------------------------------------------------- #
def test_resume_recovery_sends_decision_token_not_status(sample_create, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from app.models import Decision, DecisionChannel

    captured = {}

    async def fake_resume(handle, *, approval_id, decision, decided_by):
        captured["decision"] = decision
        return None

    monkeypatch.setattr(main, "resume_n8n", fake_resume)
    client = TestClient(main.app)

    approved = repo.create_approval(sample_create(), actor="n8n")
    repo.decide(approved["approval_id"], decision=Decision.approve, actor="alice",
                channel=DecisionChannel.api, note=None)
    r = client.post(f"/approvals/{approved['approval_id']}/resume")
    assert r.status_code == 200
    assert captured["decision"] == "approve"   # the workflow IF compares against this, NOT 'approved'

    denied = repo.create_approval(sample_create(incident_id="inc_res_deny"), actor="n8n")
    repo.decide(denied["approval_id"], decision=Decision.deny, actor="bob",
                channel=DecisionChannel.api, note=None)
    r = client.post(f"/approvals/{denied['approval_id']}/resume")
    assert r.status_code == 200
    assert captured["decision"] == "deny"
