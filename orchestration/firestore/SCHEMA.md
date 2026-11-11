# AIC Firestore Data Model â€” `approvals` & `audit_log`

Week 4 schema for the Autonomous Incident Commander human-in-the-loop approval
gate. Field names are **snake_case** and are identical across the security
rules, indexes, the future Generic Approval API, and this document.

Project id (emulator + all clients): **`aic-local`**

> **Post-security-audit access model (important):** the client (Firebase Auth +
> client SDK) path is intentionally narrow.
> - **`approvals`:** clients **cannot read, list, or create** these docs â€” the
>   `n8n.resume_webhook_url` is a bearer capability and field-level redaction is
>   impossible in rules, so the whole doc is hidden. The only client write is
>   the **decision update** (`pending -> approved/denied`) by an authorized
>   approver, constrained to the decision fields. All client reads go through
>   the API (`GET /approvals/pending`), which **strips the `n8n` map** first.
> - **`audit_log`:** clients **cannot create** rows (a self-chosen `actor` was
>   forgeable); the **Admin-SDK API is the sole writer**. Clients may **read**
>   the trail for the Web UI.
> - The Admin SDK **bypasses all rules**, so the API re-enforces every invariant
>   below in code, and those invariants are backed by tests + a least-privilege
>   service account + PITR/exports (see *Admin-SDK enforcement* at the bottom).

---

## Collection: `approvals`

One document per **incident occurrence** that needs human sign-off. Holds the
remediation plan, the risk classification, the originating alert, and the n8n
resume handle.

### Doc-id strategy

- **Server-generated ULID or UUIDv4**, e.g. `apr_01J9Z8...` (prefix optional for
  readability). NOT Firestore auto-id, because the id must be known *before* the
  doc is written so it can be embedded in the n8n resume flow and in
  Slack/Teams approve/deny buttons.
- **Do NOT** use `alert_fingerprint` as the doc id: the same alert can recur or
  flap and would collide onto one doc, overwriting an in-flight approval. Store
  the fingerprint as a queryable field instead.

### Fields

| Field | Type | Required? | Description |
|---|---|---|---|
| `approval_id` | string | yes | Equals the doc id (ULID/UUID). Denormalized for convenience. Frozen after decision. |
| `status` | string (enum) | yes | One of `pending`, `approved`, `denied`, `expired`, `executing`, `executed`, `rolled_back`, `failed`. Born `pending`. Rules allow only `pending -> approved/denied`; later lifecycle states are written by the API (Admin SDK). |
| `plan_format` | string | yes | Plan language, e.g. `hcl`. Frozen after decision. |
| `plan_summary` | string | yes | Short human-readable summary for list rendering. Frozen after decision. |
| `plan_inline` | string \| null | no | Full plan inline ONLY if small (< ~200 KB). Firestore doc cap is 1 MiB. Frozen after decision. |
| `plan_ref` | string \| null | no | GCS/Storage URI for large plans (use instead of `plan_inline`). Frozen after decision. |
| `plan_hash` | string | yes | sha256 of the full plan for tamper-evidence; frozen after decision. |
| `risk` | string (enum) | yes | `Low` \| `Med` \| `High`. Frozen after decision. |
| `risk_rationale` | string | no | Why the agent assigned that risk. Frozen after decision. |
| `remediation_summary` | string | no | Gemini's plain-English explanation of what the alert means and what the plan does (Web UI "Remediation Solution" section). Distinct from `risk_rationale`, which is only the final risk verdict. Frozen after decision. |
| `alert_type` | string | yes | e.g. `OOMKilled`, `504`, `NodePressure`. Frozen after decision. |
| `alert_payload` | map | yes | Raw Prometheus/Alertmanager JSON. Frozen after decision. |
| `alert_fingerprint` | string | no | Alertmanager dedup key (queryable, NOT the doc id). Frozen after decision. |
| `incident_id` | string | yes | Correlation id tying alert -> approval -> audit -> execution. Frozen after decision. |
| `n8n` | map | yes | Resume handle (see below). Treated as a **bearer capability** â€” NEVER exposed to clients (clients cannot read approvals at all). Frozen after decision. |
| `created_at` | timestamp | yes | Server-set creation time (`== request.time` in rules). Frozen after decision. |
| `expires_at` | timestamp | no | SLA deadline (e.g. +1h High, +4h Med/Low). TTL/sweep field. Frozen after decision (the sweep that flips to `expired` runs server-side via the Admin SDK). |
| `decided_at` | timestamp \| null | no | Set on decision (`== request.time`). One of the only client-mutable fields. |
| `decided_by` | string \| null | no | Verified decider identity (`== request.auth.uid` on the client path). One of the only client-mutable fields. |
| `decision_channel` | string (enum) | no | `web` \| `curl` \| `slack` \| `teams` \| `pagerduty` \| `api`. **On the client/Web-UI path the rules HARD-PIN this to `web`** so provenance cannot be forged; other channels are set server-side by the API (Route B). |
| `decision_note` | string \| null | no | Free-form reviewer note (string if present). One of the only client-mutable fields. |
| `schema_version` | number | yes | Schema version for migrations (start at `1`). Frozen after decision. |

> **Client decision write â€” the ONLY mutable keys.** On the rules-governed
> (Route A / Web UI) decision update, the changed-key allowlist is exactly
> **`status`, `decided_by`, `decided_at`, `decision_channel`, `decision_note`**.
> Every other field is pinned `old == new`, no new keys may appear, `decided_by`
> must equal `request.auth.uid`, `decided_at` must equal `request.time`, and
> `decision_channel` must equal `web`. The API decide transaction mirrors this
> exact allowlist.

#### `n8n` map (resume handle â€” the PUSH model)

| Field | Type | Description |
|---|---|---|
| `execution_id` | string | The paused n8n execution id. |
| `resume_webhook_url` | string | `$execution.resumeUrl` captured **in the same execution as the Wait node** (partial executions regenerate it â€” a stale URL resumes nothing). Looks like `{WEBHOOK_URL}webhook-waiting/{executionId}`. **Capability token** â€” never exposed to clients; the API strips the whole `n8n` map from `GET /approvals/pending` responses. |
| `resume_method` | string | HTTP method the Wait node expects, e.g. `POST`. |
| `workflow_id` | string | Owning workflow id. |

### Example `approvals` document

```json
{
  "approval_id": "apr_01J9Z8KQ4N3X7M2VBR5T6YH0PD",
  "status": "pending",
  "plan_format": "hcl",
  "plan_summary": "Increase memory limit of payments deploy 512Mi -> 1Gi",
  "plan_inline": "resource \"kubernetes_deployment\" \"payments\" { ... }",
  "plan_ref": null,
  "plan_hash": "sha256:9f2c1ab4...e07",
  "risk": "Med",
  "risk_rationale": "Resource bump only; no traffic shift. Reversible.",
  "remediation_summary": "The container was killed for exceeding its memory limit. The proposed plan raises the deployment's memory limit from 512Mi to 1Gi so the workload has enough headroom to run without being OOM-killed again.",
  "alert_type": "OOMKilled",
  "alert_payload": { "alertname": "OOMKilled", "pod": "payments-7c9", "namespace": "prod" },
  "alert_fingerprint": "a1b2c3d4e5f6",
  "incident_id": "inc_2026_0624_0007",
  "n8n": {
    "execution_id": "31987",
    "resume_webhook_url": "http://localhost:5678/webhook-waiting/31987",
    "resume_method": "POST",
    "workflow_id": "aic-approval-gate"
  },
  "created_at": "2026-06-24T15:04:11.218Z",
  "expires_at": "2026-06-24T19:04:11.218Z",
  "decided_at": null,
  "decided_by": null,
  "decision_channel": null,
  "decision_note": null,
  "schema_version": 1
}
```

---

## Collection: `audit_log`

Append-only, immutable trail of every meaningful action. **Written ONLY by the
Admin-SDK API** (the client `create` rule is `if false`). Immutability is
enforced by security rules (`update`/`delete` denied for everyone on the client
path) â€” and the API must also never mutate these rows (the Admin SDK bypasses
rules; see *Admin-SDK enforcement*).

### Doc-id strategy

- **ULID** doc ids â€” time-sortable, append-friendly, no hotspotting on a single
  incrementing key.

### Fields

| Field | Type | Required? | Description |
|---|---|---|---|
| `event_id` | string | yes | Equals the doc id (ULID). |
| `event_type` | string (enum) | yes | `approval_created` \| `approval_decided` \| `approval_approved` \| `approval_denied` \| `approval_expired` \| `execution_started` \| `executed` \| `rollback_started` \| `rolled_back` \| `execution_failed`. Validated server-side against this enum. |
| `approval_ref` | string | no | The related `approval_id`. |
| `incident_id` | string | no | Correlation id (same chain as the approval). |
| `actor` | string | yes | Who/what triggered it (uid/email/service/`system`). **Set server-side from the authenticated decide caller â€” never client-chosen.** |
| `channel` | string (enum) | no | `web` \| `curl` \| `slack` \| `teams` \| `pagerduty` \| `api` \| `n8n` \| `system`. |
| `timestamp` | timestamp | yes | Server-set (`FieldValue.serverTimestamp()`). |
| `before` | map \| null | no | Snapshot of mutated fields pre-change. |
| `after` | map \| null | no | Snapshot of mutated fields post-change. |
| `detail` | string | no | Free-form description. |
| `source_ip` | string \| null | no | Caller IP if known (server-observed, not client-asserted). |
| `prev_hash` | string \| null | no | **Tamper-evidence (recommended):** hash of the previous audit row. |
| `entry_hash` | string \| null | no | **Tamper-evidence (recommended):** server-computed hash over this row's canonical content + `prev_hash`, forming a chain so out-of-band reordering/deletion (even via the Admin SDK) is detectable. |
| `schema_version` | number | yes | Schema version (start at `1`). |

### Example `audit_log` document

```json
{
  "event_id": "01J9Z9F3M8QH2W0KR7B5N6YV1C",
  "event_type": "approval_approved",
  "approval_ref": "apr_01J9Z8KQ4N3X7M2VBR5T6YH0PD",
  "incident_id": "inc_2026_0624_0007",
  "actor": "tarik@securivai.example",
  "channel": "web",
  "timestamp": "2026-06-24T15:09:42.881Z",
  "before": { "status": "pending" },
  "after": { "status": "approved" },
  "detail": "Approved memory bump after reviewing HCL plan.",
  "source_ip": "10.0.4.12",
  "prev_hash": "sha256:7b1f...c4",
  "entry_hash": "sha256:0a93...e1",
  "schema_version": 1
}
```

---

## How the API endpoints map onto the data

> Week-4 note: these endpoints are **designed here but built in Week 5**. The
> mapping is documented now so the schema, rules, and indexes are correct ahead
> of implementation.

### `POST /approvals`  (n8n -> create the gate)
- Generates a ULID `approval_id`, writes one `approvals` doc with `status:
  "pending"`, the plan/risk/alert fields, and the `n8n` resume map. **This is
  the ONLY supported creation path** â€” direct-client create is denied by rules.
- Server-side create contract (the API validates; rules cannot, since the Admin
  SDK bypasses them): born `pending`; required fields present and well-typed;
  `created_at = FieldValue.serverTimestamp()`; **no** `decided_*`/`decision_*`
  fields pre-set; only the documented key set written (no unknown keys).
- **Critical ordering in n8n** (PUSH model): `LangGraph -> POST /approvals
  (persist n8n.resume_webhook_url) -> Wait (Resume on Webhook Call)`. The node
  that captures `$execution.resumeUrl` MUST be in the **same execution** as the
  Wait node, or the stored URL is stale.
- Writes an `audit_log` row `event_type: approval_created` (server-set `actor`).

### `GET /approvals/pending`  (Web UI / Route A)
- Query: `where('status','==','pending').orderBy('created_at')`.
- Requires the composite index `(status ASC, created_at ASC)` declared in
  `firestore.indexes.json` (the emulator auto-indexes; prod would throw
  `FAILED_PRECONDITION` without it).
- The API **strips the `n8n` map** from the response so the resume capability
  token never reaches a browser. (Clients cannot read `approvals` directly â€” the
  rules deny `get`/`list` â€” so this endpoint is the only read path.)

### `POST /approvals/{id}/decide`  (Route A or B -> resume n8n)
- Runs read-check + status flip + `audit_log` write in a **single Firestore
  transaction**; rejects with **409** if `status` is already non-`pending`
  (idempotency â€” a Web-UI double-click and a concurrent Slack action can't
  double-resume n8n).
- Allowed transition only: `pending -> approved | denied`. Sets `decided_at`,
  `decided_by` (verified caller), `decision_channel` (`web` for Route A; the
  actual Route-B channel server-side), optional `decision_note`. **Changed-key
  allowlist mirrors the rules:** only `status`, `decided_by`, `decided_at`,
  `decision_channel`, `decision_note` may change; plan/alert/n8n stay frozen.
- After the transaction commits, the API fires an HTTP `POST` to
  `n8n.resume_webhook_url` to resume the paused execution; the decision payload
  (decision, decided_by) is injected as the Wait node's output items.
- Writes an `audit_log` row (`approval_approved` / `approval_denied`) with a
  server-set `actor` and (recommended) the `prev_hash`/`entry_hash` chain.

### n8n resume mechanism in the data

The resume handle lives in the `approvals.n8n` map. This is the **PUSH** design:
n8n stores `$execution.resumeUrl` on the approval doc; the decide endpoint reads
it and POSTs to it to wake the same paused execution. A lightweight poll-based
watchdog (n8n `Wait(time)` + `GET /approvals/{id}` loop) is kept only as a
safety net for resumes missed due to an n8n restart or network blip.

### Expiry (designed, Week 5+)
`expires_at = created_at + SLA`. A Firestore TTL policy on `expires_at` only
*deletes* â€” it does not flip status â€” so a separate sweep flips overdue
`pending -> expired`, writes an `approval_expired` audit row, and resumes n8n
with a timeout/deny decision so no workflow hangs forever. The sweep runs
server-side (Admin SDK); rules do not grant clients any `pending -> expired`
transition.

---

## Admin-SDK enforcement (the largest residual risk â€” make it verifiable)

The Admin SDK bypasses every rule above, so the same invariants are an API
responsibility and must be *proven*, not just promised:

1. **Regression tests (Elias's harness).** Via the Admin SDK, attempt
   `update` and `delete` on an `audit_log` row, and attempt to flip
   `plan_hash`/`risk`/`alert_*` on an already-decided approval â€” assert the API
   rejects all of them. Add a test that a `decide` with the audit write removed
   fails (status flip and audit append must commit together). Add a
   reconciliation check that every decided approval has exactly one matching
   decision audit row, and no audit row references a non-existent/contradictory
   approval.
2. **Least-privilege service account.** Run the API under a dedicated SA. Back
   the create-only intent for `audit_log` with VPC-SC + a deny on Datastore
   delete (Firestore IAM is coarse), or route audit writes through a separate
   restricted service.
3. **PITR / scheduled exports.** Enable Firestore Point-in-Time Recovery and/or
   scheduled exports to an append-only bucket (object-versioning + retention
   lock) so even an Admin-SDK deletion is recoverable and detectable.
4. **Hash chain.** Populate `audit_log.prev_hash`/`entry_hash` server-side so
   reordering/selective deletion is provable out of band.
5. **Post-decision lifecycle as append, not in-place mutation.** When advancing
   `approved -> executing -> executed/rolled_back`, write only `status` +
   execution-result fields and assert (code + test) that plan/alert/decision
   fields are unchanged. Prefer modeling execution results as a separate
   immutable `executions` subcollection or additional `audit_log` rows rather
   than mutating the approval doc, so the approval is effectively
   write-once-then-decide-once.