# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Project-wide context (data flow, ownership areas, safety constraints) lives in the repo-root `../CLAUDE.md`. This file only covers what's specific to `execution/`.

## What This Directory Is

The **AIC Execution Service** — a FastAPI app that receives approved Terraform HCL from the LangGraph agent (via n8n) and applies it to the target Kubernetes cluster, with per-incident sandboxing and rollback support. This is the last hop before `terraform apply` touches real infrastructure, so correctness and isolation matter more than throughput.

## Layout

```
execution/
├── app/
│   ├── main.py                     FastAPI app, CORS, /health
│   ├── routes/remediation.py       /apply, /apply/{id}/status, /rollback
│   └── services/executor.py        TerraformExecutor: init → validate → apply, rollback
├── terraform/                      Provisions the staging EKS cluster (VPC + EKS module)
├── test_fixtures/
│   ├── oomkilled_remediation.tf    Sample remediation HCL
│   └── test_execute.sh             End-to-end curl test against a running service
├── Dockerfile                      python:3.10-slim + terraform CLI 1.8.5
└── requirements.txt
```

Note: Kubernetes/Helm/ArgoCD manifests live at the repo root under `../deployment/`, **not** inside this directory (the root README/CLAUDE.md's older references to `execution/helm/` and `execution/k8s/` are out of date).

## Common Commands

Run just this service locally:
```bash
uvicorn app.main:app --reload --port 8000    # from execution/
```

Full stack (this service + n8n + approval_api + web-ui + prometheus):
```bash
docker compose up --build      # from repo root
```

End-to-end curl test — submits sample HCL, polls status to completion:
```bash
./test_fixtures/test_execute.sh [BASE_URL]    # default http://localhost:8000
```

Provision the staging EKS cluster:
```bash
cd terraform && terraform init && terraform apply
aws eks update-kubeconfig --region us-east-1 --name aic-staging
```

Lint:
```bash
ruff check .
```

## Architecture Notes

### API surface (`app/routes/remediation.py`)

| Method | Path | Behavior |
|---|---|---|
| POST | `/apply` | Returns **202** immediately; runs pipeline in a `BackgroundTasks` coroutine. Re-submitting an `incident_id` already `running` returns **409**. |
| GET  | `/apply/{incident_id}/status` | Job record: `queued` \| `running` \| `completed` \| `failed` \| `crashed` \| `rolling_back` \| `rolled_back` \| `rollback_failed`. |
| POST | `/rollback` | Runs `terraform destroy` in the preserved sandbox. Takes `{incident_id}` in the body. Only valid when status is `completed`. |

The endpoints sit at the **root** (no `/api` prefix) because that is the contract the orchestrator calls: n8n's "Apply Fix" node POSTs to `${EXECUTION_API_URL}/apply` (with `EXECUTION_API_URL=http://execution:8000`), and the reference mock (`orchestration/mocks/mock_execution.py`) exposes the same `/apply` + `/rollback` shape. Keep this service conformant to that mock — n8n is built against it and must not be changed to fit this service.

The apply body carries the plan **inline as HCL** in `plan_inline` (not `terraform_hcl`); `plan_ref` is reserved for a future stored-plan lookup and currently returns **501**. Exactly one of `plan_inline`/`plan_ref` must be supplied. `workspace_id` is **optional** (defaults to `staging-environment`) — n8n does not send it; it is used only for log correlation, never for the sandbox path.

`incident_id` and `workspace_id` are Pydantic-validated against `^[a-zA-Z0-9_\-\.]+$` — this is the path-traversal guard for sandbox directory names. Do not weaken it.

### Job registry

Jobs are stored in an **in-memory dict** (`_registry` in `remediation.py`) protected by a `threading.Lock`. This is deliberately a placeholder — the plan is to move it to Redis or Firestore (`redis` is already in `requirements.txt` and running in Compose). State does not survive a service restart.

### Terraform executor (`app/services/executor.py`)

The pipeline runs each incident's HCL in an isolated sandbox at `/tmp/tf_sandboxes/incident_<id>/`:

1. **ISOLATE** — `mkdir` sandbox, write `remediation.tf`
2. **INIT** — `tflocal init -input=false -no-color`
3. **VALIDATE** — `tflocal validate -no-color`
4. **APPLY** — `tflocal apply -auto-approve -input=false -no-color`

Sandbox lifecycle:
- **On failure** (any phase): `shutil.rmtree` the sandbox in `finally`.
- **On success**: sandbox is **preserved** so that `rollback()` can `terraform destroy` against its `.terraform/state`. Rollback then wipes it.

Per-phase timeout is 300 s (`_TF_TIMEOUT`). Pipeline calls are synchronous — routes offload them via `asyncio.to_thread`. `validate_only()` is a lighter, backend-less pre-flight check intended for the approval gate.

### `tflocal` vs `terraform` — important

The executor invokes **`tflocal`** (the LocalStack wrapper), not `terraform`. The Dockerfile installs `terraform` but not `tflocal`; if you run the container standalone the pipeline will fail with `FileNotFoundError` and return `"'tflocal' binary not found."`. Either install `terraform-local` in the image, or switch the executor to `terraform` — do not paper over this by shelling out to a different binary path.

### Two Terraform contexts (do not confuse)

- **`execution/terraform/`** — checked-in HCL that provisions the **staging EKS cluster itself** (VPC, EKS module, node group). Run manually / via `make provision`. Uses AWS provider.
- **Per-incident remediation HCL** — generated at runtime by the LangGraph agent, POSTed to `/apply` as `plan_inline`, written to a `/tmp/tf_sandboxes/…` sandbox. Never committed. Typically uses the `kubernetes` provider against the running cluster.

The staging cluster's `terraform.tfstate` currently lives in the working directory — migrate to a remote backend (S3/GCS) before this is used by more than one operator, and to unblock wiping post-apply sandboxes in production (see the `NOTE` in `executor.run_pipeline`).

## Terraform-Related Guardrails

- The `terraform validate` phase in `run_pipeline` is the pre-apply guardrail promised by the project's safety model — do not skip it even for "trivial" HCL, and do not let a plan reach `apply` if `validate` returned non-zero.
- If a phase fails, return `{"success": False, "failed_phase": <phase>, ...}` and let the sandbox wipe run in `finally`. Do not attempt partial recovery inside a single pipeline run — retries should be a new `incident_id`.

## CI

`.github/workflows/execution.yml` (repo root) builds and pushes `execution/` on any change under `execution/**` to Docker Hub (`${DOCKERHUB_USERNAME}/execution`). Note: the root README says images go to GHCR — the actual pipeline uses Docker Hub. Tags: `sha-<sha>` always, plus `latest` on `main`.