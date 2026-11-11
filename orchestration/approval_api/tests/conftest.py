"""Pytest fixtures for the Approval API invariant tests.

These tests require a RUNNING Firestore emulator. Point at it with:

    export FIRESTORE_EMULATOR_HOST=127.0.0.1:8080
    export FIRESTORE_PROJECT_ID=aic-local
    pytest -q

If the emulator env var is not set, the whole module is skipped (so a plain
``pytest`` on a laptop without the emulator doesn't hard-fail CI-unrelated runs).

Each test gets a clean slate: the ``clean_collections`` fixture wipes the
``approvals`` and ``audit_log`` collections before every test so assertions about
row counts / atomicity are deterministic.
"""

from __future__ import annotations

import os

import pytest

# Skip the entire suite unless an emulator is configured -- we must never touch
# real Firestore from a test run.
if not os.getenv("FIRESTORE_EMULATOR_HOST"):
    pytest.skip(
        "FIRESTORE_EMULATOR_HOST not set; start the emulator to run invariant tests",
        allow_module_level=True,
    )

# Ensure a project id is present for the emulator client.
os.environ.setdefault("FIRESTORE_PROJECT_ID", "aic-local")

from app import firestore_repo as repo  # noqa: E402  (import after env is set)


def _wipe(collection_name: str) -> None:
    db = repo.get_db()
    for doc in db.collection(collection_name).stream():
        doc.reference.delete()


@pytest.fixture()
def db():
    """Raw Firestore client for assertions that read the stored docs directly."""
    return repo.get_db()


@pytest.fixture(autouse=True)
def clean_collections():
    """Empty both collections before each test for deterministic assertions."""
    _wipe("approvals")
    _wipe("audit_log")
    yield
    _wipe("approvals")
    _wipe("audit_log")


@pytest.fixture()
def sample_create():
    """A valid CreateApprovalRequest factory (Med risk by default).

    The n8n resume host is ``n8n`` -- an allowlisted host in the default
    ``N8N_RESUME_ALLOWED_HOSTS`` -- so the SSRF URL validator accepts it.
    """
    from app.models import CreateApprovalRequest, N8nHandle, Risk

    def _make(**overrides):
        data = dict(
            plan_format="hcl",
            plan_summary="Bump payments memory 512Mi -> 1Gi",
            plan_inline='resource "kubernetes_deployment" "payments" { }',
            plan_ref=None,
            plan_hash="sha256:9f2c1ab4e07",
            risk=Risk.Med,
            risk_rationale="Resource bump only; reversible.",
            alert_type="OOMKilled",
            alert_payload={"alertname": "OOMKilled", "pod": "payments-7c9"},
            alert_fingerprint="a1b2c3",
            incident_id="inc_test_0001",
            n8n=N8nHandle(
                execution_id="31987",
                resume_webhook_url="http://n8n:5678/webhook-waiting/31987",
                resume_method="POST",
                workflow_id="aic-approval-gate",
            ),
        )
        data.update(overrides)
        return CreateApprovalRequest(**data)

    return _make
