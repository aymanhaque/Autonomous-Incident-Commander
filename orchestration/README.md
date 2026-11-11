# Orchestration, API & UI (Tarik)

The connective tissue and trust layer of AIC: the n8n workflow that drives the
incident response, the Generic Approval API that gates it, the Firestore data
model + security rules behind it, and the approval Web UI.

| Subfolder | What | Status |
|---|---|---|
| [`n8n/`](n8n/) | n8n engine config + version-controlled workflow exports | **Week 4 ✅** containerized, pinned, resume-URL fixed |
| [`firestore/`](firestore/) | `approvals` + `audit_log` schema, security rules, emulator | **Week 4 ✅** schema + hardened rules + local emulator |
| `approval_api/` | Generic Approval API: `POST /approvals`, `GET /approvals/pending`, `POST /approvals/{id}/decide` | Week 5 |
| `web-ui/` | React/Streamlit approve/deny screen (Route A) | Week 6 |

## Week 4 deliverable (done)

1. **n8n in Docker** — root `docker-compose.yml` service `n8n`, pinned to
   `2.27.4`, owner-account auth, and `WEBHOOK_URL` set so "Wait for Webhook"
   resume actually works. See [n8n/README.md](n8n/README.md).
2. **Firestore schema** — `approvals` + `audit_log` collections fully specified
   in [firestore/SCHEMA.md](firestore/SCHEMA.md).
3. **Security rules** — default-deny, append-only `audit_log`, frozen-after-
   decision approvals, approver-only decisions, in
   [firestore/firestore.rules](firestore/firestore.rules). These survived an
   adversarial security review; see [../docs/security-audit.md](../docs/security-audit.md).

Plus a free-tier-safe **Firestore emulator** (opt-in `emulator` compose profile)
so the team develops without real GCP spend.

## Two things the rest of the team needs from this

- **The data contract is frozen now.** JP writes into `approvals` and the
  Approval API; Elias's harness reads `audit_log`/`test_results`. Field names and
  the status lifecycle are in [firestore/SCHEMA.md](firestore/SCHEMA.md) — code
  against that.
- **The Admin SDK bypasses the security rules.** The Week-5 Approval API (and
  anything using `firebase-admin`) is NOT constrained by `firestore.rules` — it
  must re-enforce every invariant in code. The exact list, plus the tests that
  prove it, is in SCHEMA.md → *Admin-SDK enforcement*.
