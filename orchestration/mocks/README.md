# AIC Thin Mocks

Stand-in services so the **full approval loop runs end-to-end before JP
(LangGraph) and Muhd/Ayman (execution) finish their real implementations.**
Both are FastAPI, deterministic, and require no external state.

## `mock_langgraph.py` -- plan generation

`POST /generate-plan` takes an alert payload and returns a **canned, deterministic**
response keyed by `alert_type`:

| `alert_type` | risk | plan |
|---|---|---|
| `OOMKilled` | `Med` | memory-limit bump (reversible) |
| `504` | `Low` | HPA max-replicas raise (additive) |
| `NodePressure` | `Med` | replica reduction to relieve pressure |
| `DeleteNamespace`, `DropDatabase`, `ScaleToZero`, `DeletePVC`, `NodeDrainAll` | **`High`** | destructive -- hard-stopped, never auto-approved |
| anything else | `Med` | cautious reversible noop |

`plan_hash` is the **real sha256** of `plan_inline` (prefixed `sha256:`), so the
Approval API's tamper-evidence field is meaningful. A destructive / high-blast
alert type **always** returns risk `High` (contract requirement).

Response shape:

```json
{
  "plan_format": "hcl",
  "plan_inline": "resource ...",
  "plan_summary": "...",
  "plan_hash": "sha256:...",
  "risk": "Med",
  "risk_rationale": "...",
  "alert_type": "OOMKilled",
  "alert_fingerprint": "a1b2c3"
}
```

```bash
curl -s -X POST http://localhost:8001/generate-plan \
  -H 'Content-Type: application/json' \
  -d '{"alert_type": "OOMKilled", "alert_payload": {"pod": "payments-7c9"}}'
```

## `mock_execution.py` -- apply / rollback

Stateless. Mirrors the real executor's request contract.

```bash
# apply (exactly one of plan_inline / plan_ref)
curl -s -X POST http://localhost:8000/apply \
  -H 'Content-Type: application/json' \
  -d '{"plan_inline": "resource ...", "incident_id": "inc_test_0001"}'
# -> {"status":"applied","incident_id":"inc_test_0001"}

curl -s -X POST http://localhost:8000/rollback \
  -H 'Content-Type: application/json' \
  -d '{"incident_id": "inc_test_0001"}'
# -> {"status":"rolled_back","incident_id":"inc_test_0001"}
```

## Run

```bash
cd orchestration/mocks
pip install -r requirements.txt
uvicorn mock_langgraph:app --port 8001 &
uvicorn mock_execution:app --port 8000 &
```

Or via Docker: `Dockerfile.langgraph` (port 8001) and `Dockerfile.execution`
(port 8000). Wire both into the repo `docker-compose.yml` in place of the real
`agent` / `execution` services while they're being built.
