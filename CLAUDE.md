# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

**Autonomous Incident Commander (AIC)** — an autonomous SRE system that only puts a human in the loop when the blast radius warrants it. When Prometheus fires an alert (OOMKilled pod, 504 timeout, node pressure, etc.), AIC:
1. Generates a Terraform remediation plan + Low/Medium/High risk score via a LangGraph agent
2. Writes the plan to Firestore as an approval record
3. **Low/Medium risk**: auto-decided and applied immediately — no human waits in the loop, but the decision is still recorded and audited. **High risk**: held pending for a human to explicitly approve or deny.
4. On approval: applies the Terraform plan, monitors Prometheus, auto-rolls back if metrics worsen

## Development Commands

### Run the full stack locally
```bash
cp .env.example .env   # fill in GEMINI_API_KEY, FIRESTORE_PROJECT_ID, etc.
docker compose up --build
```

Services: FastAPI execution (`localhost:8000`), n8n orchestration (`localhost:5678`), Web UI (`localhost:3000`), mock Prometheus (`localhost:9090`).

### Run the AI test harness
```bash
cd evaluation
pip install -r requirements.txt
python test_runner.py          # runs all payloads in test_data/ against the agent
streamlit run dashboard/app.py # evaluation dashboard
```

### Trigger a test incident end-to-end
```bash
# Fire a synthetic alert into n8n
curl -X POST http://localhost:5678/webhook/aic \
  -H "Content-Type: application/json" \
  -d @evaluation/test_data/oomkilled_sample.json

# Approve via REST (no UI needed)
curl -X POST http://localhost:8000/approvals/<approval_id>/decide \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve"}'
```

### Deploy to the staging Kubernetes cluster
```bash
cd execution/terraform && terraform init && terraform apply
cd ../helm && helm upgrade --install aic ./aic-chart -n aic --create-namespace
# or one-shot:
make provision
```

## Architecture

The project is split across four bounded ownership areas:

| Area | Directory | Owner | Role |
|---|---|---|---|
| AI Brain | `agent/` | Jean-Pascal | LangGraph agent, prompt templates, Terraform plan generation, blast-radius risk classifier |
| Infrastructure & Execution | `execution/` | Ayman | FastAPI execution service, Docker/K8s/Helm, Terraform provisioning, auto-rollback, Prometheus |
| Orchestration, API & UI | `orchestration/` | Tarik | n8n workflows, Generic Approval REST API, Firestore schemas/security rules, Web UI |
| AI Evaluation | `evaluation/` | Elias | Python test harness, 20+ synthetic alert scenarios, Streamlit dashboard, regression CI |

### Data flows

**Incident response (production):**
```
Prometheus Alert → n8n → LangGraph API → Firestore (approval record)
→ Low/Medium risk: n8n auto-decides "approve" and continues immediately
→ High risk: held pending → Web UI / REST approve → n8n resumes
→ Execution API → terraform apply → Prometheus watch → auto-rollback if regressed
```

**AI quality assurance (CI):**
```
evaluation/test_data/*.json → test_runner.py → LangGraph API
→ validate HCL + terraform validate + risk consistency
→ Firestore test_results → Streamlit dashboard
→ GitHub Actions posts to Slack/GitHub comment on every PR to main
```

### Key design constraints

- **Only High-risk plans wait for a human** — the risk classifier gates them so they can never be auto-approved; a person must explicitly approve or deny.
- **Low/Medium-risk plans are auto-approved and applied without waiting** — the risk classifier is the only thing standing between an alert and a live `terraform apply`, so it (and `terraform validate`, below) must stay conservative.
- **All Terraform plans run `terraform validate`** before being eligible for approval or auto-approval.
- Every approval/denial — human or auto-decided — is written to an immutable Firestore `audit_log` collection.
- Secrets live in Kubernetes Secrets / env vars only — never in code.

## CI/CD

- GitHub Actions builds and pushes Docker images to GHCR on every push.
- The test harness (`python test_runner.py`) runs automatically on every PR to `main` — **any change touching `agent/` must pass the test harness before merge**.
- ArgoCD/Flux handles GitOps sync of Kubernetes manifests to the staging cluster.
- Run `pre-commit`/linting locally before pushing (per-component conventions are in `docs/`).

## Required Credentials (`.env`)

```
GEMINI_API_KEY=...
FIRESTORE_PROJECT_ID=...
FIRESTORE_CREDENTIALS_PATH=./secrets/firestore-service-account.json
PROMETHEUS_URL=http://prometheus:9090
N8N_WEBHOOK_URL=http://n8n:5678/webhook/aic
```

Ollama can substitute for Gemini for fully offline development.
