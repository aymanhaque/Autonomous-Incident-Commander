# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Directory Is

The `agent/` directory is the **AI brain** of AIC. It exposes a FastAPI service (port 8001) wrapping a LangGraph pipeline that transforms raw Prometheus/AlertManager webhook payloads into Terraform HCL remediation plans with risk scores.

## Development Commands

### Run locally (standalone)
```bash
# Install dependencies
pip install -r requirements.txt

# Set required env vars, then start the server
AIC_GEMINI_MODEL=gemini-2.5-flash uvicorn agent.api.main:app --host 0.0.0.0 --port 8001 --reload
```

### Run via Docker
```bash
docker build -t aic-agent:latest .
docker run -p 8001:8001 \
  -e AIC_GEMINI_MODEL=gemini-2.5-flash \
  -e AIC_LLM_TEMPERATURE=0.2 \
  aic-agent:latest
```

### Test a plan generation request
```bash
curl -X POST http://localhost:8001/generate-plan \
  -H "Content-Type: application/json" \
  -d '{"alerts": [{"labels": {"alertname": "OOMKilled", "namespace": "prod", "pod": "api-xyz", "severity": "critical"}, "annotations": {"description": "Pod was OOMKilled"}}]}'
```

### Run the evaluation harness (integration tests)
```bash
cd ../evaluation
pip install -r requirements.txt
python test_runner.py   # fires all test_data/*.json payloads against the agent
```

## Architecture

### LangGraph Pipeline

The graph is defined in `langgraph_agent/graph.py` and runs these nodes in sequence:

```
parse_alert → generate_plan → summarize_remediation → validate_plan → classify_risk
                                                                              ↓
                                                          (routing: should_hard_stop?)
                                                         ↙ High risk          ↘ Low/Medium
                                                    hard_stop                  END
                                                        ↓
                                                       END
```

All pipeline state flows through a single `AgentState` TypedDict (`langgraph_agent/state.py`).

### Node Responsibilities

| File | Node | What it does |
|---|---|---|
| `nodes/parse_alert.py` | `parse_alert` | Extracts alertname, namespace, pod, severity, description from the first alert in the payload |
| `nodes/generate_plan.py` | `generate_plan` | Calls Gemini to produce Terraform HCL; strips markdown code fences via `_clean_hcl()` |
| `nodes/summarize_remediation.py` | `summarize_remediation` | Calls Gemini for a 2–3 sentence plain-English summary; failure here is non-fatal |
| `nodes/validate_plan.py` | `validate_plan` | Validates HCL syntax via `python-hcl2`; sets `validation_passed` and `error` |
| `nodes/classify_risk.py` | `classify_risk` | Delegates to `risk_validator/blast_radius.py` |
| `routing.py` | — | Returns `"hard_stop"` if `risk_score == "High"`, else `"continue"` |

### Risk Classifier (`risk_validator/blast_radius.py`)

Scoring is rule-based, evaluated in order:

1. **Severity floor**: `critical` alert → floor is High; `warning` → floor is Medium
2. **Dangerous patterns** (text scan before HCL parse): `replicas = 0` or `deletion_protection = false` → High
3. **High-risk resource types**: networking, IAM, databases, cluster-level resources → High
4. **Medium-risk resource types**: Kubernetes workloads, ConfigMaps, Secrets, Helm releases → Medium
5. **Final score** = max(computed level, severity floor)

The result of this classifier is the only gate between an alert and a live `terraform apply` for Low/Medium plans — keep its logic conservative.

### API Layer (`api/`)

- `api/schemas.py` — `PlanRequest` (AlertManager webhook shape) and `PlanResponse` Pydantic models
- `api/main.py` — two routes:
  - `POST /generate-plan` — synchronous, returns `PlanResponse`
  - `POST /generate-plan/stream` — SSE stream emitting typed JSON events: `alert_parsed`, `token`, `plan_complete`, `summary`, `validation`, `risk`, `error`, `done`

### Prompts (`prompts/`)

- `plan_generation.py` — instructs Gemini to output **only** raw HCL with no markdown, making the smallest, most conservative change possible
- `remediation_summary.py` — instructs Gemini to write 2–3 plain-English sentences, no markdown

### Configuration (`config.py`)

| Env var | Default | Purpose |
|---|---|---|
| `AIC_GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `AIC_LLM_TEMPERATURE` | `0.2` | LLM temperature |

The LLM client is lazily initialized and cached (`@cache`) so it is reused across requests.

## Key Invariants

- **Hard stop is final**: A `risk_score == "High"` always routes to `hard_stop`, which sets an error and prevents auto-approval. Do not add any path that bypasses this.
- **Summary failures are non-fatal**: `summarize_remediation` catches its own exceptions; pipeline continues regardless.
- **HCL fence stripping is required**: Gemini often wraps output in ` ```hcl ` blocks despite the system prompt. `_clean_hcl()` in `generate_plan.py` handles this.
- **No unit tests in this directory**: Testing is entirely through the evaluation harness in `../evaluation/`. Any change to agent logic must be validated by running `python test_runner.py` there.
