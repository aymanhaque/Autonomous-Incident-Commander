#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────────
# AIC Execution Service — end-to-end curl test
#
# Simulates an approved RemediationPayload arriving from n8n/the agent.
# Requires: curl, jq
#
# Usage:
#   chmod +x test_execute.sh
#   ./test_execute.sh [BASE_URL]          # defaults to http://localhost:8000
# ────────────────────────────────────────────────────────────────────────────
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
INCIDENT_ID="inc-oomkill-demo-$(date +%s)"
WORKSPACE_ID="staging-environment"

# ── Inline HCL (matches oomkilled_remediation.tf) ───────────────────────────
read -r -d '' HCL << 'HCL_EOF' || true
terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.31"
    }
  }
}

provider "kubernetes" {
  config_path    = "~/.kube/config"
  config_context = "docker-desktop"
}

resource "kubernetes_deployment" "oomkilled_fix" {
  metadata {
    name      = "aic-oomkilled-demo"
    namespace = "default"
    labels = {
      "app"                    = "aic-oomkilled-demo"
      "aic/remediation-action" = "memory-limit-increase"
    }
  }
  spec {
    replicas = 2
    selector {
      match_labels = { app = "aic-oomkilled-demo" }
    }
    template {
      metadata {
        labels = { app = "aic-oomkilled-demo" }
      }
      spec {
        container {
          name  = "app"
          image = "nginx:1.27-alpine"
          resources {
            requests = { memory = "256Mi", cpu = "100m" }
            limits   = { memory = "512Mi", cpu = "500m" }
          }
          port { container_port = 80 }
        }
      }
    }
  }
}
HCL_EOF

# ────────────────────────────────────────────────────────────────────────────
echo "============================================================"
echo "  AIC Execution Service — curl test"
echo "  BASE_URL    : ${BASE_URL}"
echo "  INCIDENT_ID : ${INCIDENT_ID}"
echo "  WORKSPACE   : ${WORKSPACE_ID}"
echo "============================================================"

# ── Step 0: health check ────────────────────────────────────────────────────
echo ""
echo "▶ Step 0: Health check"
curl -sf "${BASE_URL}/health" | jq .

# ── Step 1: submit the remediation payload ──────────────────────────────────
echo ""
echo "▶ Step 1: POST /apply"

PAYLOAD=$(jq -n \
  --arg incident_id  "$INCIDENT_ID"  \
  --arg workspace_id "$WORKSPACE_ID" \
  --arg plan_inline  "$HCL"          \
  '{incident_id: $incident_id, workspace_id: $workspace_id, plan_inline: $plan_inline}')

SUBMIT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/apply" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

HTTP_CODE=$(echo "$SUBMIT_RESPONSE" | tail -n1)
BODY=$(echo "$SUBMIT_RESPONSE" | sed '$d')

echo "HTTP $HTTP_CODE"
echo "$BODY" | jq .

if [ "$HTTP_CODE" != "202" ]; then
  echo "✗ Expected 202 Accepted, got $HTTP_CODE — aborting."
  exit 1
fi

# ── Step 2: poll for completion ─────────────────────────────────────────────
echo ""
echo "▶ Step 2: Polling /apply/${INCIDENT_ID}/status …"
echo "  (terraform init downloads providers — allow up to ~60s on first run)"

POLL_INTERVAL=5
MAX_POLLS=24   # 2 minutes total
POLLS=0
STATUS="queued"

while [ "$STATUS" = "queued" ] || [ "$STATUS" = "running" ]; do
  sleep $POLL_INTERVAL
  POLLS=$((POLLS + 1))

  STATUS_RESPONSE=$(curl -s "${BASE_URL}/apply/${INCIDENT_ID}/status")
  STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')

  echo "  [poll ${POLLS}/${MAX_POLLS}] status=${STATUS}"

  if [ "$POLLS" -ge "$MAX_POLLS" ]; then
    echo "✗ Timed out waiting for completion."
    echo "$STATUS_RESPONSE" | jq .
    exit 1
  fi
done

echo ""
echo "▶ Final status response:"
echo "$STATUS_RESPONSE" | jq .

# ── Step 3: report result ───────────────────────────────────────────────────
echo ""
if [ "$STATUS" = "completed" ]; then
  echo "✓ Execution completed successfully."
  echo ""
  echo "▶ Step 3 (optional): Trigger rollback"
  echo "  curl -s -X POST ${BASE_URL}/rollback -H 'Content-Type: application/json' -d '{\"incident_id\": \"${INCIDENT_ID}\"}' | jq ."
elif [ "$STATUS" = "failed" ]; then
  echo "✗ Execution failed. Check the server logs for the full terraform output."
  FAILED_PHASE=$(echo "$STATUS_RESPONSE" | jq -r '.result.failed_phase // "unknown"')
  echo "  Failed phase: ${FAILED_PHASE}"
  exit 1
else
  echo "⚠ Unexpected terminal status: ${STATUS}"
  exit 1
fi
