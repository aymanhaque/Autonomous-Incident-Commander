# AIC Generic Approval API

The human-in-the-loop **approval gate** for the Autonomous Incident Commander.
Lives in `orchestration/approval_api/` (Tarik's ownership area).

```
Prometheus alert -> n8n -> LangGraph (plan + risk)
  -> POST /approvals            (this API: create PENDING record + store n8n resume handle)
  -> n8n PAUSES on "Wait for Webhook"
  -> human decides via Web UI (Route A) or curl/Slack/Teams/PagerDuty (Route B)
  -> POST /approvals/{id}/decide (this API: transactional decision + audit row, then POST n8n resume URL)
  -> n8n resumes -> (if approved) Execution API applies the Terraform plan
```

## Why the API re-enforces everything

The Firebase **Admin SDK bypasses `firestore.rules` unconditionally.** So every
invariant the rules protect on the client path is **re-enforced in code** in
`app/firestore_repo.py`. Each check is annotated with its invariant number:

1. Approvals are **born `pending`**; create rejects any pre-set decision field, non-pending status, **or unknown key** (the repo mirrors the rules' `hasOnly` key bound, not just Pydantic).
2. Only `pending -> approved|denied`; re-deciding a non-pending approval is **409**.
3. On decide, **only** `status/decided_by/decided_at/decision_channel/decision_note` change; the decide write set is asserted to be a subset of that allowlist **before** the write, and `update()` (not `set()`) physically leaves every other field frozen.
4. `audit_log` is **append-only** (no update/delete method exists).
5. The audit `actor`/`decided_by` is **always the authenticated caller**, never a body field.
6. The status flip and its audit row commit in **one transaction**; the audit `before` is derived from the doc read inside that transaction.
7. The `n8n` map / `resume_webhook_url` is **never** returned in any response.
8. All inputs are validated (Pydantic v2, `extra='forbid'` on create; size caps on `plan_inline` and `alert_payload`).

## Trust boundary & authentication(read this)

Two independent layers gate the **write** endpoints (`POST /approvals`, `/decide`, `/resume`):

1. **Service token (the API's own auth).** Send `Authorization: Bearer $API_SERVICE_TOKEN`.
   - If `API_SERVICE_TOKEN` is **set**, a mismatched/missing token is **401**.
   - If it is **unset** and the API is **not** talking to the emulator, every write **fails closed with 503** -- a prod deploy can never accidentally run open. In emulator/dev mode an unset token is allowed so local runs stay frictionless.
2. **Decider identity (`X-Actor`).** The `decided_by` and audit `actor` come from the
   **authenticated principal** -- the `X-Actor` header in dev (fallback `unknown`). In prod a
   gateway / JWT middleware verifies the caller and populates that header. The decision body
   carries only `decision`, `decision_note`, `decision_channel` -- there is deliberately **no
   field** to assert an identity, so a Route-B caller cannot forge who decided.

### SSRF guard on the n8n resume URL

`n8n.resume_webhook_url` is **caller-supplied** and later POSTed server-side, so it is validated
at the model boundary:

- scheme must be `http`/`https`;
- host must be in **`N8N_RESUME_ALLOWED_HOSTS`** (default `n8n,localhost,127.0.0.1`);
- hosts resolving to link-local/metadata addresses (e.g. `169.254.169.254`) are blocked;
- `resume_method` is constrained to **`N8N_RESUME_ALLOWED_METHODS`** (default `POST,PUT`);
- the outbound client uses `follow_redirects=False` so a 302 can't bypass the allowlist.

### CORS

No CORS middleware is installed unless **`CORS_ALLOW_ORIGINS`** is set (comma-separated). It is
pinned to those exact origins with `allow_credentials=False` -- never a wildcard with credentials.

## Configuration (env)

| Var | Default | Purpose |
|---|---|---|
| `FIRESTORE_PROJECT_ID` / `GCLOUD_PROJECT` | `aic-local` | Firestore project id. |
| `FIRESTORE_EMULATOR_HOST` | *(unset)* | `host:port`, no scheme. Set => emulator + anonymous creds. |
| `FIRESTORE_CREDENTIALS_PATH` | *(unset)* | Service-account JSON for prod. |
| `API_SERVICE_TOKEN` | *(unset)* | Shared bearer token for write endpoints. **Unset + non-emulator => 503 (fail-closed).** |
| `ACTOR_HEADER` / `ACTOR_FALLBACK` | `X-Actor` / `unknown` | Human-identity header + dev fallback. |
| `N8N_RESUME_ALLOWED_HOSTS` | `n8n,localhost,127.0.0.1` | SSRF host allowlist for the resume URL. |
| `N8N_RESUME_ALLOWED_METHODS` | `POST,PUT` | Allowed resume HTTP methods. |
| `N8N_RESUME_TIMEOUT_S` | `10.0` | Resume-call timeout. |
| `CORS_ALLOW_ORIGINS` | *(empty)* | Comma-separated allowed origins; empty => no CORS. |
| `MAX_PLAN_INLINE_BYTES` | `204800` | Inline-plan size cap. |
| `MAX_ALERT_PAYLOAD_BYTES` | `262144` | `alert_payload` size cap. |

## Run locally (against the Firestore emulator)

The emulator is wired up in `orchestration/firestore/` + the repo `docker-compose.yml`.

```bash
# 1) Start the Firestore emulator (project id: aic-local)
docker compose --profile emulator up firestore

# 2) Run the API against it (host:port, NO http:// scheme)
cd orchestration/approval_api
pip install -r requirements.txt
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8080
export FIRESTORE_PROJECT_ID=aic-local
# API_SERVICE_TOKEN may be omitted in emulator mode (writes are allowed).
uvicorn app.main:app --reload --port 8080
```

Or the whole stack: `docker compose up --build` from the repo root.

## Endpoints

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/approvals` | n8n creates a pending gate. Returns `{approval_id, status}` only. | service token |
| `GET`  | `/approvals/pending?limit=N` | Route A: pending list, oldest first, **n8n stripped**. | -- |
| `GET`  | `/approvals/{id}` | Fetch one, **n8n stripped**. `404` if missing. | -- |
| `POST` | `/approvals/{id}/decide` | Route A/B: transactional decision + audit + n8n resume. | service token |
| `POST` | `/approvals/{id}/resume` | Idempotently re-drive a missed n8n resume for an already-decided gate. | service token |
| `GET`  | `/health` | Liveness. | -- |

## Route B curl examples

Create a gate (normally n8n does this). In emulator/dev mode the service token
may be omitted; in prod add `-H 'Authorization: Bearer $API_SERVICE_TOKEN'`:

```bash
curl -s -X POST http://localhost:8080/approvals \
  -H 'Content-Type: application/json' \
  -H 'X-Actor: n8n-service' \
  -d '{
    "plan_format": "hcl",
    "plan_summary": "Bump payments memory 512Mi -> 1Gi",
    "plan_inline": "resource \"kubernetes_deployment\" \"payments\" { }",
    "plan_hash": "sha256:9f2c...e07",
    "risk": "Med",
    "risk_rationale": "Resource bump only; reversible.",
    "alert_type": "OOMKilled",
    "alert_payload": {"alertname": "OOMKilled", "pod": "payments-7c9"},
    "alert_fingerprint": "a1b2c3",
    "incident_id": "inc_2026_0701_0001",
    "n8n": {
      "execution_id": "31987",
      "resume_webhook_url": "http://n8n:5678/webhook-waiting/31987",
      "resume_method": "POST",
      "workflow_id": "aic-approval-gate"
    }
  }'
# -> {"approval_id":"apr_...","status":"pending"}  (no n8n map echoed)
```

> Note: `resume_webhook_url` must target an allowlisted host
> (`N8N_RESUME_ALLOWED_HOSTS`); an internal/metadata URL is rejected with 422.

Approve it from a terminal (Route B). Identity comes from `X-Actor`, not the body:

```bash
curl -s -X POST http://localhost:8080/approvals/apr_XXXX/decide \
  -H 'Content-Type: application/json' \
  -H 'X-Actor: tarik@securivai.example' \
  -d '{"decision": "approve", "decision_channel": "curl", "decision_note": "LGTM"}'
# -> {"approval": { ... no n8n map ... }, "resume_warning": null}
```

A second decide on the same id returns **409** (idempotency guard):

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  http://localhost:8080/approvals/apr_XXXX/decide \
  -H 'X-Actor: someone-else' -H 'Content-Type: application/json' \
  -d '{"decision": "deny"}'
# -> 409
```

If the decision committed but the resume POST failed (non-null `resume_warning`),
re-drive it without touching the decision -- safe to call repeatedly:

```bash
curl -s -X POST http://localhost:8080/approvals/apr_XXXX/resume
# -> {"approval_id":"apr_XXXX","resume_warning":null}
```

## Tests

```bash
cd orchestration/approval_api
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8080
export FIRESTORE_PROJECT_ID=aic-local
pytest -q
```

`tests/test_invariants.py` runs against the emulator and covers every invariant
(born-pending; reject pre-set decision fields; reject unknown keys; pending-only
transition; 409 on re-decide; frozen fields on decide; audit row written
atomically with a derived `before`; audit actor is server-set not body; n8n map
never in responses) plus the SSRF URL/method allowlist and channel coercion.
