# `test_results` — handoff for the evaluation harness (Elias)

Where the AI evaluation harness stores per-test-case scores so the dashboard can
chart agent accuracy over time. The collection schema and rules are owned by the
orchestration slice (Tarik); the harness and dashboard are owned by evaluation
(Elias). This folder is the whole contract.

## Connect (no cloud credentials — we run on the local emulator)

There is no cloud Firestore for this project; everything runs against the local
Firestore emulator, so there are no credentials to hand out.

```bash
# from the repo root, start just the emulator:
docker compose --profile emulator up -d firestore
```

Point the harness at it:

```
FIRESTORE_EMULATOR_HOST=127.0.0.1:8080
FIRESTORE_PROJECT_ID=aic-local
```

**The one gotcha:** `firebase-admin` (and a bare `firestore.Client()`) still try
to load Application Default Credentials even in emulator mode and crash on a
machine with no service account. Build the client with anonymous creds directly
(see `write_result_example.py`). Writes from that client take the owner/Cloud
path, so the `test_results` rules (`allow create: if false` for browsers) do not
block the harness — they only stop a browser forging results.

## Schema — one document per (test case, run), append-only

| Field | Type | Notes |
| --- | --- | --- |
| `run_id` | string | groups one harness/CI run (git short SHA or a run uuid) |
| `agent_version` | string | the agent commit/version under test |
| `test_case_id` | string | which file from `evaluation/test_data/` (e.g. `oomkilled_pod`) |
| `alert_type` | string | `OOMKilled` \| `GatewayTimeout504` \| `NodeMemoryPressure` \| ... |
| `passed` | bool | overall pass/fail for this case |
| `generation_time_ms` | number | agent latency for this case |
| `risk_expected` | string | expected `Low` \| `Med` \| `High` |
| `risk_actual` | string | the agent's classification |
| `risk_correct` | bool | `risk_expected == risk_actual` |
| `hcl_valid` | bool | output parsed as HCL |
| `terraform_validate_passed` | bool | passed `terraform validate` |
| `failure_mode` | string \| null | tag on failure, e.g. `invalid_hcl`, `wrong_risk` |
| `created_at` | timestamp | `SERVER_TIMESTAMP`; sort/trend key |

Doc id is auto-generated (`collection.add(...)`). Rows are never updated or
deleted — one row per case per run, so the dashboard can trend accuracy.

## Dashboard queries (indexes already declared in `firestore.indexes.json`)

- one run's detail: `where('run_id','==',X).order_by('created_at')`
- per-alert-type trend: `where('alert_type','==',X).order_by('created_at', DESC)`

Pass rate, average `generation_time_ms`, and risk misclassification rate are
computed in the dashboard from these fields.

## Run the example

```bash
pip install google-cloud-firestore
FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 python write_result_example.py
```

Want different fields? It is the orchestration slice's collection — ping Tarik
and it changes here (schema + rules + indexes) in one place.
