# Security Audit (living document)

Tarik owns the final security audit (Week 8). This file is started in Week 4 and
grows as components land, so the audit is continuous rather than a last-week
scramble.

## Method

Each component is reviewed adversarially through four lenses: **authorization
bypass**, **audit/data integrity**, **input validation & spoofing**, and
**secrets / least privilege**. Findings are fixed, then re-verified.

## Week 4 — Firestore data layer (audited & fixed)

The `approvals` / `audit_log` schema and `firestore.rules` were reviewed and
hardened before landing. Findings that were fixed:

| Sev | Finding | Fix |
|---|---|---|
| 🔴 Critical | Any signed-in user could **read an approval**, exposing `n8n.resume_webhook_url` — a bearer capability that resumes remediation, bypassing the approver check, the decide endpoint, and the audit log. | Clients can't read `approvals` at all (`allow get, list: if false`). The Web UI reads via `GET /approvals/pending`, which strips the `n8n` map server-side. |
| 🔴 Critical | `audit_log` was append-only but **not tamper-evident** — any signed-in user could append rows with a forged `actor`/`event_type`, fabricating clean "approved" history. | Client `create` denied; the Admin-SDK API is the sole writer and sets `actor` from the verified caller atomically with the status flip. Optional `prev_hash`/`entry_hash` chain documented. |
| 🟠 High | Decision writes froze only a subset of fields, so an approver could rewrite `plan_inline`/`risk`/etc. while `plan_hash` stayed frozen (tamper-evidence defeat); new keys could be injected. | `changedKeys().hasOnly([...])` allowlist + every non-decision field pinned `old == new`. |
| 🟠 High | `decision_channel`/`decision_note` provenance unpinned (forgeable from the web). | Client path hard-pins `decision_channel == 'web'`; Route-B channels set server-side. |
| 🟠 High | Firestore emulator API + Suite UI published on `0.0.0.0` — an **unauthenticated full read/write surface exposed to the LAN**. | Host ports bound to `127.0.0.1` (the in-container bind stays `0.0.0.0` for the compose network). |
| 🟡 Med | `N8N_SECURE_COOKIE=false` / http could ride into a prod copy of `.env`. | `.env.example` is secure-by-default; insecure dev values isolated to a gitignored override. |

Full finding-by-finding changelog: see the orchestration deliverable's
`CHANGELOG-audit.md` (carried in this PR / branch).

## Week 5-7 — Approval API + orchestration (audited & fixed)

The Admin-SDK enforcement risk carried from Week 4 is **CLOSED**: every invariant
is re-enforced in `approval_api` code and proven by a 23-test suite run live
against the emulator (`FIRESTORE_EMULATOR_HOST=... pytest -q` -> 23 passed).

| Sev | Finding | Fix / status |
|---|---|---|
| 🔴 Critical | Admin SDK bypasses `firestore.rules`, so a compromised/buggy API could forge history or mutate frozen fields. | All 8 invariants re-enforced in `firestore_repo.py` (born-pending, pending-only 409, changed-key allowlist, atomic status+audit, server-set actor, n8n stripped) + 23 passing tests. |
| 🟠 High | Write endpoints could run open in a misconfigured deploy. | Service token gate that **fails closed (503)** if `API_SERVICE_TOKEN` is unset outside emulator mode; 401 on mismatch. |
| 🟠 High | `n8n.resume_webhook_url` is caller-supplied and POSTed server-side (SSRF primitive to internal/metadata hosts). | Scheme + host allowlist at the model boundary, link-local/metadata IPs blocked, `follow_redirects=False` on the resume call. Verified: metadata-endpoint + disallowed-host tests pass. |
| 🟡 Med | The Firestore **emulator credential path had never run** — `firestore.client()` resolved Application Default Credentials even in emulator mode and crashed on any box without a service account (would have blocked CI + every teammate). | Emulator mode builds a `google.cloud.firestore.Client` with `AnonymousCredentials`; production keeps the Admin SDK. |
| 🟡 Med | n8n workflow read service URLs/token via `$env`, which n8n 2.x **denies in expressions by default** (workflow errored before creating any approval). | `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` set in compose with a comment explaining why; targets stay in `.env`, not hardcoded in the workflow. |
| 🟢 Low | New `GET /approvals/recent` (History tab) could shadow `GET /approvals/{id}`. | Literal route declared **before** the path-param route; History query filters on `decided_at > epoch` so pending rows never leak into history. |

## Route B integration surface

`POST /approvals/{id}/decide` is the sole decision endpoint for every channel
(UI, curl, Slack, Teams, PagerDuty, ServiceNow). Identity is the `X-Actor`
header (server-verified in prod), never a body field, so a Route-B caller cannot
forge who decided. One decision wins (transactional 409). See
[integration-guide.md](integration-guide.md).

## Still open before final sign-off

- n8n has no auth beyond the owner account + localhost bind — any reverse-proxy
  / remote exposure needs an auth layer first (Week 8, if the demo is exposed).
- Audit `prev_hash`/`entry_hash` chain remains null placeholders — optional
  tamper-evidence hardening, documented in SCHEMA.md, not required for the demo.
- Least-privilege service account + PITR apply only to a real GCP deploy (the
  graded demo runs on the emulator, so no cloud IAM surface exists yet).

## Week 8 final checklist

- [x] No hardcoded secrets: `.env` gitignored, `.env.example` secure-by-default, token via env.
- [x] Firestore rules enforce admin-only reads + append-only audit (client path).
- [x] API re-enforces all invariants in code (Admin SDK bypasses rules) — 23 tests.
- [x] SSRF guard on the caller-supplied resume URL.
- [x] Emulator host ports bound to `127.0.0.1` (no LAN exposure of the rules-bypassing surface).
- [ ] If deployed to real GCP: least-privilege service account + budget alert (out of scope for the emulator demo).

## Pending (as components land)

- `agent/` — prompt-injection surface from alert payloads into the LLM (JP).
- `execution/` — Terraform apply blast radius, K8s Secrets, minimal IAM (Ayman).
- Final Week-8 pass: no hardcoded keys, strict rules, minimal IAM across all
  services.
