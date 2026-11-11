import type { Approval } from "./types";

const now = Date.now();
const at = (msFromNow: number) => new Date(now + msFromNow).toISOString();

export const MOCK_APPROVALS: Approval[] = [
  {
    approval_id: "01JQZ8HIGH0RISKNODEPOOL",
    status: "pending",
    plan_format: "hcl",
    plan_summary: "Drain and replace node gke-prod-pool-2 under sustained memory pressure",
    plan_inline: `# node pool change -> classified HIGH (blast radius: entire pool)
resource "google_container_node_pool" "prod_pool" {
  name       = "gke-prod-pool-2"
  cluster    = "aic-prod"
  node_count = 4
  management {
    auto_repair  = true
    auto_upgrade = true
  }
}
# ~ node_pool will be recreated -> drains 4 nodes, reschedules ~36 pods`,
    plan_hash: "sha256:9f2c1ab4e07",
    risk: "High",
    risk_rationale: "Recreates a node pool; whole-pool blast radius.",
    alert_type: "NodeMemoryPressure",
    alert_payload: { alertname: "NodeMemoryPressure", namespace: "kube-system", severity: "critical", instance: "gke-prod-pool-2" },
    alert_fingerprint: "a1b2c3",
    incident_id: "inc_2026_0705_0488",
    created_at: at(-3 * 60 * 1000),
    expires_at: at(12 * 60 * 1000),
    decided_at: null,
    decided_by: null,
    schema_version: 1,
  },
  {
    approval_id: "01JQZ8MEDOOMPAYMENTS512",
    status: "pending",
    plan_format: "hcl",
    plan_summary: "Raise payments-api memory limit 512Mi -> 1Gi after repeated OOMKilled",
    plan_inline: `resource "kubernetes_deployment_v1" "payments_api" {
  metadata { name = "payments-api"  namespace = "payments" }
  spec { template { spec { container {
    name = "payments-api"
    resources {
      limits   = { memory = "1Gi" }    # was 512Mi
      requests = { memory = "512Mi" }
    }
  } } } }
}`,
    plan_hash: "sha256:1c77de99a02",
    risk: "Med",
    risk_rationale: "Resource bump only; reversible.",
    alert_type: "OOMKilled",
    alert_payload: { alertname: "OOMKilled", namespace: "payments", severity: "warning", instance: "payments-api-7c9" },
    alert_fingerprint: "d4e5f6",
    incident_id: "inc_2026_0705_0489",
    created_at: at(-7 * 60 * 1000),
    expires_at: at(33 * 60 * 1000),
    decided_at: null,
    decided_by: null,
    schema_version: 1,
  },
  {
    approval_id: "01JQZ8LOWCHECKOUTHPA610",
    status: "pending",
    plan_format: "hcl",
    plan_summary: "Scale checkout-api HPA maxReplicas 6 -> 10 to absorb a 504 spike",
    plan_inline: `resource "kubernetes_horizontal_pod_autoscaler_v2" "checkout" {
  metadata { name = "checkout-api"  namespace = "storefront" }
  spec {
    min_replicas = 3
    max_replicas = 10   # was 6
    scale_target_ref { kind = "Deployment"  name = "checkout-api" }
  }
}`,
    plan_hash: "sha256:5a0be31c7f4",
    risk: "Low",
    risk_rationale: "Replica ceiling bump; easily reverted.",
    alert_type: "HighErrorRate504",
    alert_payload: { alertname: "HighErrorRate504", namespace: "storefront", severity: "warning", instance: "checkout-api" },
    alert_fingerprint: "77aa88",
    incident_id: "inc_2026_0705_0490",
    created_at: at(-1 * 60 * 1000),
    expires_at: at(48 * 60 * 1000),
    decided_at: null,
    decided_by: null,
    schema_version: 1,
  },
  {
    approval_id: "01JQZ8LOWORDERSPDBADD02",
    status: "pending",
    plan_format: "hcl",
    plan_summary: "Add PodDisruptionBudget (minAvailable 2) to orders-api",
    plan_inline: `resource "kubernetes_pod_disruption_budget_v1" "orders" {
  metadata { name = "orders-api-pdb"  namespace = "orders" }
  spec {
    min_available = 2
    selector { match_labels = { app = "orders-api" } }
  }
}`,
    plan_hash: "sha256:b1122cc33dd",
    risk: "Low",
    risk_rationale: "Additive policy object; no workload change.",
    alert_type: "FrequentRestarts",
    alert_payload: { alertname: "FrequentRestarts", namespace: "orders", severity: "info", instance: "orders-api" },
    alert_fingerprint: "99bb00",
    incident_id: "inc_2026_0705_0491",
    created_at: at(-12 * 60 * 1000),
    expires_at: at(2 * 60 * 1000),
    decided_at: null,
    decided_by: null,
    schema_version: 1,
  },
];
