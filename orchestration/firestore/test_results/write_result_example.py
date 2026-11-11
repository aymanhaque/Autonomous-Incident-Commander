"""Minimal example: write one test_results row to the local Firestore emulator.

Run:
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 python write_result_example.py

Uses AnonymousCredentials directly so the client does NOT try to load
Application Default Credentials (which crashes on a box with no service account,
even against the emulator). This is the same pattern the Approval API uses.
"""

from __future__ import annotations

import os

from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore

PROJECT_ID = os.environ.get("FIRESTORE_PROJECT_ID", "aic-local")
os.environ.setdefault("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")


def get_db() -> firestore.Client:
    return firestore.Client(project=PROJECT_ID, credentials=AnonymousCredentials())


def write_result(db: firestore.Client, **fields) -> str:
    row = {
        "run_id": None,
        "agent_version": None,
        "test_case_id": None,
        "alert_type": None,
        "passed": None,
        "generation_time_ms": None,
        "risk_expected": None,
        "risk_actual": None,
        "risk_correct": None,
        "hcl_valid": None,
        "terraform_validate_passed": None,
        "failure_mode": None,
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    row.update(fields)
    _, ref = db.collection("test_results").add(row)
    return ref.id


if __name__ == "__main__":
    db = get_db()
    doc_id = write_result(
        db,
        run_id="demo-run-001",
        agent_version="jp-agent@abc123",
        test_case_id="oomkilled_pod",
        alert_type="OOMKilled",
        passed=True,
        generation_time_ms=812,
        risk_expected="Med",
        risk_actual="Med",
        risk_correct=True,
        hcl_valid=True,
        terraform_validate_passed=True,
        failure_mode=None,
    )
    print(f"wrote test_results/{doc_id}")

    total = sum(1 for _ in db.collection("test_results").stream())
    print(f"test_results now holds {total} row(s)")
