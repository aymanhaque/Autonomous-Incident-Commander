# Test Data — Synthetic Prometheus Alert Payloads

This folder contains synthetic (fake) Prometheus alert payloads used to test 
the AIC's AI agent. Each file simulates a real infrastructure incident that 
the agent must analyze and generate a Terraform fix for.

---

## Alert Files

### 1. oomkilled_pod.json
A container in the `payment-service` pod was killed because it ran out of memory.
This is one of the most common Kubernetes incidents.
- **Severity:** Critical
- **Expected AI response:** Increase memory limits for the container

### 2. gateway_timeout_504.json
The API gateway is returning 504 errors, meaning requests are timing out before
getting a response from backend services.
- **Severity:** Critical
- **Expected AI response:** Scale up backend pods or increase timeout thresholds

### 3. node_memory_pressure.json
A worker node is running critically low on memory (8% remaining), putting all
pods on that node at risk.
- **Severity:** Warning
- **Expected AI response:** Drain the node or increase node memory capacity

### 4. cpu_throttling.json
The checkout service container is being CPU throttled 85% of the time, meaning
it keeps hitting its CPU limit and slowing down.
- **Severity:** Warning
- **Expected AI response:** Increase CPU limits for the checkout service container

### 5. disk_pressure.json
A worker node only has 5% disk space remaining, which can cause pods to be
evicted and services to crash.
- **Severity:** Critical
- **Expected AI response:** Expand disk size or clean up unused resources on the node

### 6. pod_crash_looping.json
The auth service pod has restarted 10 times in 15 minutes, meaning something
is repeatedly causing it to crash.
- **Severity:** Critical
- **Expected AI response:** Investigate and restart the pod with increased resources
or redeploy a stable version

### 7. high_error_rate.json
The order service is returning errors on 45% of all requests over the last
10 minutes, meaning nearly half of all orders are failing.
- **Severity:** Critical
- **Expected AI response:** Scale up the service or roll back to a previous version

---

## How These Are Used

These JSON files are fed into the test harness (`test_runner.py`) which sends
each alert to Jean-Pascal's LangGraph AI agent and checks:
- Did the agent generate valid Terraform (HCL) code?
- Is the risk score (Low/Med/High) appropriate for the alert type?
- How long did it take to generate a response?

Results are stored in Firestore and displayed on the Streamlit dashboard.

---

## Alert Format

All alerts follow the standard Prometheus AlertManager webhook format:
- `receiver` — who receives the alert (n8n webhook)
- `status` — firing or resolved
- `labels` — metadata about the alert (name, severity, affected resource)
- `annotations` — human readable summary and description
- `startsAt` — when the alert started firing