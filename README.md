# Autonomous Incident Commander (AIC)

An autonomous, human-in-the-loop SRE system that detects infrastructure incidents, generates a remediation plan with an LLM agent, classifies the risk of that plan, routes it for approval, and then executes and monitors the fix — with full audit logging and automated AI quality evaluation built in from day one.

---

## 1. Overview

When a Prometheus alert fires (OOMKilled pod, 504 timeout, node pressure, etc.), AIC:

1. **Generates a fix** — A LangGraph-based agent turns the alert into a structured Terraform (HCL) remediation plan and classifies its risk as **Low / Medium / High**.
2. **Pauses for approval** — The plan is written to Firestore as a pending approval. A human can approve or deny it either through a **Web UI** or through a **plain REST call** (curl, Postman, Slack, Teams, PagerDuty).
3. **Executes safely** — Once approved, the execution service applies the Terraform plan, watches Prometheus for regressions, and **auto-rolls back** if the fix makes things worse.
4. **Proves it works** — A parallel evaluation pipeline runs the agent against a growing library of synthetic incident scenarios on every pull request, tracking accuracy, latency, and failure modes over time.

The project is split across four ownership areas:

| Area | Owner | Responsibility |
|---|---|---|
| AI Brain (Plan Generation & Risk) | Jean-Pascal | LangGraph agent, prompt engineering, Terraform plan generation, Low/Med/High risk classification |
| Infrastructure & Execution | Ayman | Docker, Kubernetes, Terraform provisioning, CI/CD, Helm, auto-rollback, Prometheus/observability |
| Orchestration, API & UI | Tarik | n8n workflows, Generic Approval API, Firestore data models, Web UI, security |
| AI Evaluation & Test Data | Elias | Test harness, synthetic alert datasets, regression testing, performance dashboard |

---

## 2. Architecture

### Main execution flow (incident response)

```
Prometheus Alert
      │
      ▼
     n8n  ──────────►  LangGraph API (generate Terraform plan + risk score)
      │
      ▼
  Firestore: create pending approval  (POST /approvals)
      │
      ▼
  n8n pauses ("Wait for Webhook")
      │
      ├── Route A: Web UI polls GET /approvals/pending, shows Approve/Deny
      └── Route B: curl / Postman / Slack / Teams / PagerDuty
      │
      ▼
  POST /approvals/{id}/decide   (Approve or Deny)
      │
      ▼
  n8n resumes
      ├── Approved → Execution API → apply Terraform → monitor Prometheus → auto-rollback if needed
      └── Denied   → abort, log rejection
```

### Evaluation & validation flow (AI quality assurance)

```
test_data/*.json (synthetic alerts)
      │
      ▼
  Test Harness (Python)  ──────►  LangGraph API (real or mocked)
      │
      ▼
  Validate: valid HCL? terraform validate passes? risk score consistent?
      │
      ▼
  Firestore: test_results collection
      │
      ▼
  Evaluation Dashboard (Streamlit): pass rate, latency, failure breakdown, risk accuracy
      │
      ▼
  GitHub Actions CI: runs on every PR → posts results to Slack / GitHub comment
```

---

## 3. Tech Stack

**AI / Agent**
- LangGraph (agent orchestration)
- LLM: Gemini Flash (or local Ollama as a fallback/offline option)
- Rule-based fallback generator for low-confidence cases

**Execution & Infrastructure**
- FastAPI (execution service)
- Docker / Docker Compose
- Kubernetes (staging cluster — MicroK8s/k3s-style), Helm charts
- Terraform (plan generation target + provisioning)
- Prometheus (metrics, alerting, rollback triggers)
- ArgoCD / Flux (GitOps sync)
- GitHub Actions (CI/CD) + GHCR (container registry)

**Orchestration, API & UI**
- n8n (workflow orchestration, "Wait for Webhook" pattern)
- Generic Approval API — FastAPI or Firebase Cloud Functions
- Firestore (approvals, audit_log, test_results collections)
- React / Streamlit Web UI

**Evaluation**
- Python test harness (`test_runner.py`)
- Streamlit evaluation dashboard
- Synthetic alert dataset (20+ scenarios: OOMKilled, 504 timeout, node pressure, etc.)

---

## 4. Project Layout

```
aic/
├── agent/                      # Jean-Pascal — AI Brain
│   ├── langgraph_agent/        # LangGraph graph definition, nodes
│   ├── prompts/                # Prompt templates for plan generation
│   ├── risk_validator/         # "Blast Radius" risk classifier (Low/Med/High)
│   └── fallback_generator/     # Rule-based fallback plan generator
│
├── execution/                  # Ayman — Infrastructure & Execution
│   ├── app/                    # FastAPI execution service
│   ├── terraform/               # Terraform modules + staging cluster provisioning
│   ├── helm/                   # Helm chart for the AIC system
│   ├── k8s/                    # Raw K8s manifests, Secrets
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── orchestration/              # Tarik — Orchestration, API & UI
│   ├── n8n/                    # n8n workflow exports
│   ├── approval_api/           # Generic Approval API (POST /approvals, GET /approvals/pending, POST /approvals/{id}/decide)
│   ├── firestore/              # Firestore schemas + security rules
│   └── web-ui/                 # React/Streamlit approval UI
│
├── evaluation/                 # Elias — AI Evaluation & Test Data
│   ├── test_data/              # Synthetic Prometheus alert payloads (20+)
│   ├── test_runner.py          # Test harness entry point
│   ├── dashboard/               # Streamlit evaluation dashboard
│   └── reports/                # AI Performance Reports, chaos test results
│
├── .github/
│   └── workflows/              # CI: build/push images, run test harness on PR
│
├── docs/
│   ├── architecture.md
│   ├── security-audit.md
│   └── test-harness-guide.md
│
├── .env.example
├── docker-compose.yml           # Top-level compose: FastAPI + Redis + mock Prometheus + n8n
└── README.md
```

---

## 5. Prerequisites

Make sure you have the following installed locally:

- **Docker** & **Docker Compose** (v2+)
- **Git**
- **Python 3.10+**
- **Node.js 18+** (for n8n and the React UI)
- **kubectl** + a local Kubernetes cluster for staging (MicroK8s, k3s, or minikube)
- **Terraform CLI**
- **Helm**

You'll also need credentials for:
- An LLM provider — **Gemini API key**, or a local **Ollama** install if running fully offline
- **Firebase/Firestore** project credentials (service account JSON)
- (Optional) Slack/Teams/PagerDuty webhook URLs if you want Route B notifications

---

## 6. Setup & Running with Docker

### 6.1 Clone the repo

```bash
git clone https://github.com/<org>/aic.git
cd aic
```

### 6.2 Configure environment variables

```bash
cp .env.example .env
```

Fill in `.env` with at minimum:

```
GEMINI_API_KEY=...
FIRESTORE_PROJECT_ID=...
FIRESTORE_CREDENTIALS_PATH=./secrets/firestore-service-account.json
PROMETHEUS_URL=http://prometheus:9090
N8N_WEBHOOK_URL=http://n8n:5678/webhook/aic
```

### 6.3 Bring up the core stack

```bash
docker compose up --build
```

This starts:
- `fastapi-execution` — the execution service (port `8000`)
- `redis` — caching/queueing for the execution layer
- `mock-prometheus` — local Prometheus instance for testing alerts
- `n8n` — orchestration engine (port `5678`)
- `web-ui` — approval dashboard (port `3000`)

### 6.4 Verify it's running

| Service | URL |
|---|---|
| FastAPI execution docs | http://localhost:8000/docs |
| n8n editor | http://localhost:5678 |
| Approval Web UI | http://localhost:3000 |
| Mock Prometheus | http://localhost:9090 |

### 6.5 Trigger a test incident

Send a synthetic alert to n8n's webhook to kick off the full flow (generate plan → pending approval → approve via curl → execute):

```bash
curl -X POST http://localhost:5678/webhook/aic \
  -H "Content-Type: application/json" \
  -d @evaluation/test_data/oomkilled_sample.json
```

Approve it via Route B (pure API), no UI required:

```bash
curl -X POST http://localhost:8000/approvals/<approval_id>/decide \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve"}'
```

### 6.6 Deploying to the staging Kubernetes cluster

```bash
cd execution/terraform
terraform init
terraform apply

cd ../helm
helm upgrade --install aic ./aic-chart -n aic --create-namespace
```

A top-level `Makefile` is also provided for one-command provisioning:

```bash
make provision   # terraform apply + helm install in one step
```

---

## 7. Running the Test Harness & Evaluation Dashboard

```bash
cd evaluation
pip install -r requirements.txt
python test_runner.py
```

This runs every payload in `test_data/` against the LangGraph agent (or a mocked version), validates the generated Terraform, checks risk-score consistency, and writes results to the `test_results` Firestore collection.

Launch the dashboard:

```bash
streamlit run dashboard/app.py
```

The dashboard shows overall pass rate, average generation time, failure breakdown by alert type, and risk score distribution/misclassification rate.

---

## 8. CI/CD

- **GitHub Actions** builds and pushes Docker images to **GHCR** on every push.
- The **test harness runs automatically on every pull request to `main`**, posting pass/fail results as a GitHub comment or to a Slack channel — this gates any change to the agent against regressions.
- **ArgoCD/Flux** handles GitOps sync of Kubernetes manifests to the staging cluster.

---

## 9. Safety & Risk Controls

- All generated Terraform plans are run through `terraform validate` before being eligible for approval.
- Plans are classified **Low / Medium / High** risk based on blast radius; **High-risk changes are hard-stopped** and cannot be auto-approved.
- Every approval/denial is written to an immutable Firestore `audit_log`.
- No hardcoded credentials — secrets are stored in Kubernetes Secrets / environment variables, with minimal IAM permissions and strict Firestore security rules.

---

## 10. Roadmap Summary

| Week | Focus |
|---|---|
| 4 | Foundation — repo, Docker skeletons, Firestore schema, initial test dataset |
| 5 | Core logic — LLM plan generation, staging cluster provisioning, Approval API, baseline test harness |
| 6 | Risk validation — Blast Radius classifier, Helm deployment, Web UI, 20+ test scenarios, regression CI |
| 7 | Full integration — fallback generator, auto-rollback, GitOps, full performance benchmark + AI report |
| 8 | Chaos testing, security audit, stress testing, final demo & deliverables |

**Final deliverables:** GitHub repo with CI/CD, Web UI, Generic Approval API, test harness + dashboard, 10-minute demo video, 1-page security audit, 1-page AI performance report.

---

## 11. Contributing

- Branch protection is enabled on `main` — all changes go through a PR.
- Any change touching the agent (`agent/`) must pass the automated test harness before merge.
- Run `pre-commit`/linting locally before pushing (see `docs/` for per-component conventions).

---

## 12. License

Add your license of choice here (e.g. MIT) before publishing.