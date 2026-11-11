CHANGELOG â€” Week 4 AIC deliverable, applying the adversarial security audit.
All findings triaged below; valid ones (every critical/high/medium plus the
relevant low/info hardening) applied. Files kept mutually consistent:
collections (approvals, audit_log), snake_case fields, project id aic-local,
ports (n8n 5678 / Firestore 8080 / UI 4000), and env var names all match across
docker-compose.yml, .env.example, docker-compose.override.yml.example,
firebase.json, firestore.rules, firestore.indexes.json, SCHEMA.md, README.md.

=== firestore.rules (the airtight default-deny target) ===

[CRITICAL â€” resume-URL read exposure] APPLIED. approvals `allow get, list` was
`if isSignedIn()`, exposing n8n.resume_webhook_url (a bearer capability) to any
authenticated user, who could POST it to resume remediation and bypass
isApprover(), the decide endpoint, and the audit log. Field-level redaction is
impossible in rules, so the whole doc is now hidden: `allow get, list: if false`.
All client reads go through GET /approvals/pending, which strips the n8n map.

[CRITICAL/HIGH â€” forgeable audit_log] APPLIED. audit_log create previously let
any signed-in user write an arbitrary actor / event_type, fabricating
approval_approved rows (append-only != tamper-evident). Client create is now
`if false`; the Admin-SDK API is the sole writer and sets actor from the
authenticated decide caller atomically with the status flip. get/list kept for
the Web UI; update/delete remain `if false`. Documented prev_hash/entry_hash
chain in SCHEMA.md for true tamper-evidence.

[HIGH â€” incomplete approvals freeze + no key bounding] APPLIED. The update rule
now (a) pins EVERY non-decision field old==new â€” added approval_id, plan_format,
plan_inline, plan_ref, risk_rationale, alert_fingerprint, expires_at,
schema_version to the existing plan_summary/plan_hash/risk/alert_type/
alert_payload/n8n/created_at/incident_id; and (b) bounds the change set with
`diff(resource.data).changedKeys().hasOnly(['status','decided_by','decided_at',
'decision_channel','decision_note'])` so no frozen field can drift and no new
arbitrary key can be injected in the decide write. This closes the plan_inline/
plan_ref tamper-evidence-defeat hole (plan_hash was frozen but the plan body
was not).

[HIGH â€” unpinned decision_channel/decision_note provenance] APPLIED. The
client/Route-A path now hard-pins `decision_channel == 'web'` (Route B channels
are set server-side by the API, which bypasses rules) and requires
decision_note to be a string if changed. Provenance can no longer be forged from
the web UI.

[MEDIUM/HIGH â€” open approvals create with pre-injectable fields] APPLIED.
approvals create previously allowed any signed-in user to mint gates and, since
hasAll() doesn't bound keys, to pre-seed decided_*/decision_* and an
attacker-controlled n8n.resume_webhook_url (SSRF/planted capability) that the
freeze checks would carry forward. Client create is now `if false` (the
Admin-SDK API is the only creator). The full server-side create contract
(hasOnly + hasAll + born-pending + no decision fields + server created_at) is
documented inline as a comment and in SCHEMA.md for the API to enforce.

[INFO â€” default-deny, decided_by/decided_at verification, pending-only
transition, isSignedIn-first gating] CONFIRMED CORRECT, kept as-is. The
catch-all `match /{document=**} { allow read,write: if false }` stays LAST;
resource.data.status=='pending' + request.resource.data.status in
['approved','denied'] still enforces the single legal transition and rules-layer
idempotency; decided_by==request.auth.uid and decided_at==request.time still
prevent decider/timestamp spoofing; isApprover() still requires the custom
claim. The low-severity "created_at is timestamp" guard was judged unnecessary
(the ==request.time equality already forces a timestamp) so not added, to keep
the rule readable â€” noted here as deliberately declined.

=== docker-compose.yml ===

[HIGH â€” Firestore ports bound 0.0.0.0 / LAN-exposed] APPLIED. Changed the bare
`${FIRESTORE_PORT}:8080` / `${FIRESTORE_UI_PORT}:4000` mappings to
`127.0.0.1:${FIRESTORE_PORT}:8080` and `127.0.0.1:${FIRESTORE_UI_PORT}:4000`,
mirroring the n8n localhost bind. The unauthenticated emulator REST API + Suite
UI data editor (both bypass firestore.rules, both can edit audit_log) are no
longer reachable from the LAN. The in-container 0.0.0.0 bind in firebase.json is
correct and unchanged (containers reach it over the compose network); only the
host publish is scoped. Added a comment explaining the two-layer bind.

[HIGH â€” n8n has no enforced auth] APPLIED (defense-in-depth + explicit
requirement). Added `N8N_USER_MANAGEMENT_DISABLED=false`, a loud AUTH WARNING
comment that the 127.0.0.1 bind is the ONLY control and must not be widened or
fronted without adding auth, and a README step to claim the owner account
immediately on first boot. Kept N8N_RUNNERS_ENABLED and
N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS.

=== .env.example + docker-compose.override.yml.example (NEW) ===

[MEDIUM â€” insecure cookie/http default rides into prod] APPLIED structurally.
.env.example is now SECURE-BY-DEFAULT: N8N_PROTOCOL=https,
N8N_SECURE_COOKIE=true, WEBHOOK_URL=https://aic.example.com/. The insecure dev
values (http + non-Secure cookie + localhost webhook) moved into a new committed
template docker-compose.override.yml.example, which the dev copies to the
gitignored docker-compose.override.yml (auto-merged by compose). A
`cp .env.example .env` for a real deployment is now secure unless the dev
deliberately opts into insecurity. Added a note that https+false is a
misconfiguration. README and the new .gitignore (Appendix B) updated to ignore
the override.

=== firebase.json ===

[LOW â€” Suite UI is an unauthenticated full read/write surface] APPLIED (note +
the host bind from the compose fix). Kept the UI enabled (needed for the Rules
Playground / audit deliverable) but added a SECURITY NOTE that it bypasses rules
and must never be published beyond 127.0.0.1, and clarified that the 0.0.0.0
in-container host is complementary to the 127.0.0.1 host-side publish (not a
contradiction). Rules + indexes wiring unchanged.

=== firestore.indexes.json ===

No security findings. Unchanged except confirmed consistent: the composite
(status ASC, created_at ASC) still backs GET /approvals/pending with snake_case
created_at. Optional (status, risk, created_at) index retained.

=== SCHEMA.md ===

Updated to match the hardened rules: documented that clients cannot read/list/
create approvals and cannot create audit_log (Admin-SDK is the sole writer);
listed the exact client-mutable decision key allowlist; pinned decision_channel
to 'web' on the client path; marked every approvals field frozen-after-decision;
added audit_log prev_hash/entry_hash hash-chain fields and a server-set/
never-client-chosen note on actor and source_ip; added an "Admin-SDK
enforcement" section turning the prose "the API must also enforce it" caveats
into concrete, testable controls (regression tests for audit immutability +
frozen-field tampering + atomic decide/audit + reconciliation; least-privilege
service account; PITR/append-only exports; hash chain; lifecycle-as-append).

=== README.md ===

Updated for all of the above: secure-by-default setup flow with the dev override
step; 127.0.0.1 binds for all three ports; the unauthenticated-surfaces warning;
the "claim the n8n owner immediately" step; revised Rules Playground checklist
(denied client reads/creates of approvals, denied audit_log create, denied
audit update/delete, the approver decision-update allow/deny cases); a note that
firebase-admin in tests bypasses rules (use a client-SDK/Auth-emulator context
to exercise rules); the Admin-SDK enforcement items and an Auth-emulator item in
Deferred; .gitignore (Appendix B) for .env, the override, and the data dir; and
Appendix C reproducing the dev override template.

=== Findings explicitly declined / deferred (with reason) ===

- Cross-document transactional atomicity between the approvals decide and the
  audit_log append (medium): Firestore rules CANNOT enforce cross-doc atomicity,
  so this is correctly an API + test guarantee, documented in SCHEMA.md
  (Admin-SDK enforcement #1) rather than added to rules.
- Constraining client audit_log event_type per-principal (medium): moot â€” client
  audit_log create is now fully denied (`if false`), which is strictly stronger
  than enum-gating per principal.
- "created_at is timestamp" explicit guard (low): declined; ==request.time
  already forces a timestamp value. Noted for transparency.
- Admin-SDK can still defeat every immutability guarantee (high): cannot be
  fixed in rules by definition (Admin SDK bypasses rules). Converted from a
  prose caveat into the testable/IAM/PITR controls in SCHEMA.md so it is
  verifiable rather than hand-waved; full implementation is Week 5.