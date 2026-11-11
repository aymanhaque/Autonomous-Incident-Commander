import type { Approval } from '../../types/approval'

export const mockApprovals: Approval[] = [
  {
    id: 'apr-001',
    status: 'pending',
    risk_level: 'low',
    created_at: '2026-07-07T09:32:15Z',
    alert: {
      alertname: 'OOMKilled',
      namespace: 'production',
      pod: 'payment-worker-7d9f8b-xvkpq',
      severity: 'warning',
      startsAt: '2026-07-07T09:31:02Z',
      labels: { job: 'payment-service', team: 'payments' },
      annotations: {
        summary: 'Container OOMKilled in production/payment-worker',
        description: 'Container payment-worker was OOMKilled — memory limit 256Mi exceeded.',
      },
    },
    remediation_summary: 'The payment-worker container was killed for exceeding its 256Mi memory limit, and usage has been trending up 18% over the past week. The proposed plan raises the LimitRange default to 512Mi (with a 256Mi request) so the workload has enough headroom without changing replica counts.',
    terraform_plan: `resource "kubernetes_limit_range" "payment_service" {
  metadata {
    name      = "payment-service-limits"
    namespace = "production"
  }
  spec {
    limit {
      type = "Container"
      default = {
        memory = "512Mi"
        cpu    = "250m"
      }
      default_request = {
        memory = "256Mi"
        cpu    = "100m"
      }
      max = {
        memory = "1Gi"
        cpu    = "500m"
      }
    }
  }
}`,
    events: [
      { id: 'e1', source: 'prometheus', type: 'warning', message: 'OOMKilled: payment-worker-7d9f8b-xvkpq (exit code 137)', timestamp: '2026-07-07T09:31:02Z' },
      { id: 'e2', source: 'agent',      type: 'info',    message: 'Alert received — starting plan generation', timestamp: '2026-07-07T09:32:15Z' },
      { id: 'e3', source: 'agent',      type: 'info',    message: 'Querying Prometheus for memory usage trend (7d)', timestamp: '2026-07-07T09:32:17Z' },
      { id: 'e4', source: 'agent',      type: 'success', message: 'Terraform plan generated — risk: LOW', timestamp: '2026-07-07T09:32:31Z' },
    ],
  },
  {
    id: 'apr-002',
    status: 'pending',
    risk_level: 'medium',
    created_at: '2026-07-07T10:15:42Z',
    alert: {
      alertname: 'HTTPRequestErrorRate',
      namespace: 'production',
      severity: 'critical',
      startsAt: '2026-07-07T10:14:09Z',
      labels: { job: 'api-gateway', team: 'platform' },
      annotations: {
        summary: 'High 504 error rate on api-gateway',
        description: '504 error rate at 14.3% (threshold 5%) on api-gateway for past 5 minutes.',
      },
    },
    remediation_summary: 'Upstream request timeouts (504s) on api-gateway are caused by CPU throttling at 89% utilization against a 1-3 replica HPA range. The proposed plan raises the autoscaling policy to 3-10 replicas with a 60% CPU target so the service can scale out before requests start timing out.',
    terraform_plan: `resource "kubernetes_horizontal_pod_autoscaler_v2" "api_gateway" {
  metadata {
    name      = "api-gateway-hpa"
    namespace = "production"
  }
  spec {
    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = "api-gateway"
    }
    min_replicas = 3
    max_replicas = 10
    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type                = "Utilization"
          average_utilization = 60
        }
      }
    }
  }
}`,
    events: [
      { id: 'e1', source: 'prometheus', type: 'error',   message: 'HTTPRequestErrorRate = 14.3% on api-gateway (threshold: 5%)', timestamp: '2026-07-07T10:14:09Z' },
      { id: 'e2', source: 'agent',      type: 'info',    message: 'Alert received — analyzing HPA and deployment config', timestamp: '2026-07-07T10:15:42Z' },
      { id: 'e3', source: 'agent',      type: 'warning', message: 'Upstream CPU at 89% — throttling detected', timestamp: '2026-07-07T10:15:44Z' },
      { id: 'e4', source: 'agent',      type: 'success', message: 'Terraform plan generated — risk: MEDIUM', timestamp: '2026-07-07T10:16:01Z' },
    ],
  },
  {
    id: 'apr-003',
    status: 'pending',
    risk_level: 'high',
    created_at: '2026-07-07T11:03:07Z',
    alert: {
      alertname: 'NodeMemoryPressure',
      namespace: 'kube-system',
      node: 'k8s-node-03',
      severity: 'critical',
      startsAt: '2026-07-07T11:01:55Z',
      labels: { job: 'node-exporter', team: 'platform' },
      annotations: {
        summary: 'Node k8s-node-03 under critical memory pressure',
        description: 'k8s-node-03 at 97.4% memory utilization — kernel OOM killer active.',
      },
    },
    remediation_summary: 'Node k8s-node-03 is at 97.4% memory with the kernel OOM killer evicting pods non-deterministically across the 12 production pods it hosts. The only safe remediation is to cordon and drain the node so those workloads reschedule onto the 2 remaining nodes, which have enough headroom to absorb them — this requires manual SRE sign-off due to the brief disruption involved.',
    terraform_plan: `resource "kubernetes_node_taint" "drain_k8s_node_03" {
  metadata {
    name = "k8s-node-03"
  }
  taint {
    key    = "node.kubernetes.io/unschedulable"
    value  = "true"
    effect = "NoSchedule"
  }
}

resource "null_resource" "drain_node" {
  triggers = {
    node    = "k8s-node-03"
    version = "1"
  }
  provisioner "local-exec" {
    command = <<-EOT
      kubectl drain k8s-node-03 \\
        --ignore-daemonsets \\
        --delete-emptydir-data \\
        --force \\
        --grace-period=60
    EOT
  }
}`,
    events: [
      { id: 'e1', source: 'prometheus', type: 'error',   message: 'NodeMemoryPressure: k8s-node-03 at 97.4% — OOM killer active', timestamp: '2026-07-07T11:01:55Z' },
      { id: 'e2', source: 'agent',      type: 'info',    message: 'Alert received — assessing node workload distribution', timestamp: '2026-07-07T11:03:07Z' },
      { id: 'e3', source: 'agent',      type: 'error',   message: 'Node drain required — 12 pods will be disrupted', timestamp: '2026-07-07T11:03:12Z' },
      { id: 'e4', source: 'agent',      type: 'warning', message: 'Plan generated — risk: HIGH. Blocked pending SRE sign-off.', timestamp: '2026-07-07T11:03:29Z' },
    ],
  },
]
