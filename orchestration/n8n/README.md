# n8n — Orchestration Engine

n8n runs the **approval-gate workflow**: it receives a Prometheus alert, calls
the LangGraph agent for a plan, writes a pending approval to Firestore via the
Generic Approval API, then **pauses on a "Wait for Webhook" node** until a human
approves or denies — at which point it resumes and (if approved) calls the
execution service.

n8n is defined in the **root `docker-compose.yml`** (service `n8n`). This folder
holds **version-controlled workflow exports**.

## Run it

```bash
cp .env.example .env          # set N8N_ENCRYPTION_KEY (openssl rand -hex 16)
docker compose up -d n8n      # or `docker compose up` for the whole stack
```

Open <http://localhost:5678> and **create the owner account on first boot**.
n8n 2.x uses owner-account user management — claim it immediately.

> **Heads-up (fixed in Week 4):** the original compose set
> `N8N_BASIC_AUTH_ACTIVE/USER/PASSWORD`. Those vars were **removed in n8n 1.0**
> and are silently ignored in 2.x — the stack only *looked* protected. Auth is
> now the owner account above. The image is also pinned (`:2.27.4`, was
> `:latest`).

## The resume-URL gotcha (the most important thing here)

n8n builds "Wait for Webhook" **resume URLs** from `WEBHOOK_URL` / `N8N_HOST` /
`N8N_PROTOCOL`. If those are wrong, the workflow pauses but **nothing can ever
resume it** — the classic failure of this whole design.

- Default `WEBHOOK_URL=http://n8n:5678/` (set in `.env`). The **Approval API**
  resumes the workflow from inside the `aic` Docker network, so it must address
  n8n by its **service hostname** `n8n`, not `localhost`.
- The resume URL is captured as `$execution.resumeUrl` and **must be read in the
  same execution as the Wait node** (partial re-runs regenerate it — a stale URL
  resumes nothing). It is stored on the approval doc as `n8n.resume_webhook_url`
  (see [../firestore/SCHEMA.md](../firestore/SCHEMA.md)) and is a **bearer
  capability** — the API never exposes it to browsers.
- Testing the resume URL by hand from your laptop? The `n8n` hostname won't
  resolve on the host — override `WEBHOOK_URL=http://localhost:5678/` in `.env`.

## The approval-gate workflow (`workflows/aic-approval-gate.json`)

The committed workflow implements the whole orchestration:

```
Alert Webhook (POST /webhook/aic)
  -> Normalize Alert            (Code: alert_type from Alertmanager labels, incident_id)
  -> Generate Plan              (POST $LANGGRAPH_API_URL/generate-plan, retry x1 after 10s)
  -> Create Approval Gate       (POST $APPROVAL_API_URL/approvals, Bearer token + X-Actor,
                                 sends n8n.resume_webhook_url = $execution.resumeUrl)
  -> Wait For Decision          (parks; resumes on POST to the resume URL)
  -> Approved?                  ($json.body.decision === 'approve')
       true  -> Apply Fix       (POST $EXECUTION_API_URL/apply, RETRY ONCE AFTER 10s)
       false -> Denied - Abort  (no-op; nothing is applied)
```

Service URLs and the token come from `$env` (`LANGGRAPH_API_URL`,
`APPROVAL_API_URL`, `EXECUTION_API_URL`, `API_SERVICE_TOKEN` — all in `.env`,
passed to the container via `env_file`). Point the URL vars at the mocks or at
JP/Ayman's real services without touching the workflow.

### Import + activate (CLI, no UI needed)

```bash
docker compose exec n8n n8n import:workflow \
  --input=/home/node/.n8n/workflows/workflows/aic-approval-gate.json
docker compose exec n8n n8n list:workflow          # note the workflow id
docker compose exec n8n n8n update:workflow --id=<ID> --active=true
docker compose restart n8n                          # register the production webhook
```

### Fire a test incident

```bash
curl -s -X POST http://localhost:5678/webhook/aic \
  -H "Content-Type: application/json" \
  -d @evaluation/test_data/oomkilled_pod.json
# -> a pending approval appears at GET :8090/approvals/pending
# approve/deny via the Web UI or curl (see docs/integration-guide.md); the
# workflow resumes and (on approve) calls the execution /apply.
```

## Exporting / importing workflows (the version-control convention)

n8n stores workflows in its own DB (the `n8n_data` volume), **not** in this
folder — the `:ro` mount here is just where committed exports live. The mount is
read-only, so **export via `docker compose cp`**, not into the mount:

```bash
# Export from the running container, then copy out and commit:
docker compose exec n8n n8n export:workflow --all --separate --output=/tmp/wf
docker compose cp n8n:/tmp/wf ./orchestration/n8n/workflows

# Import committed exports into a fresh n8n (e.g. a teammate's first run):
docker compose exec n8n n8n import:workflow --separate \
  --input=/home/node/.n8n/workflows/workflows
```

## Status

- **Done (Week 4):** n8n containerized, pinned, owner-auth, resume-URL config
  corrected so pause/resume works.
- **Done (Week 5-7):** the approval-gate workflow above — alert-in → LangGraph →
  POST /approvals → Wait → decide → resume → execution, with the Week-7 retry
  (execution call retries once after 10s). Verified end-to-end against the
  emulator + mocks.
- **Route B adapters:** no n8n work needed — any tool POSTs the same decide
  endpoint; see [docs/integration-guide.md](../../docs/integration-guide.md).
