# ────────────────────────────────────────────────────────────────────────────
# AIC Sample Remediation — OOMKilled fix
#
# Doubles the memory limit/request on a demo deployment to resolve an
# OOMKilled alert. Targets a local Kubernetes cluster (minikube / docker-desktop).
#
# Usage:
#   terraform init
#   terraform apply -auto-approve
#   terraform destroy -auto-approve   # rollback
# ────────────────────────────────────────────────────────────────────────────

terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.31"
    }
  }
}


provider "kubernetes" {
  # Reads ~/.kube/config by default.
  # Change `config_context` to match your local cluster context name:
  #   kubectl config get-contexts
  config_path    = "~/.kube/config"
  config_context = "docker-desktop" # or "minikube", "kind-kind", etc.
}

resource "kubernetes_deployment" "oomkilled_fix" {
  metadata {
    name      = "aic-oomkilled-demo"
    namespace = "default"

    labels = {
      "app"                    = "aic-oomkilled-demo"
      "aic/remediation-action" = "memory-limit-increase"
      "aic/managed-by"         = "autonomous-incident-commander"
    }
  }

  spec {
    # Two replicas so the fix is visible across the ReplicaSet.
    replicas = 2

    selector {
      match_labels = {
        app = "aic-oomkilled-demo"
      }
    }

    template {
      metadata {
        labels = {
          app = "aic-oomkilled-demo"
        }
      }

      spec {
        container {
          name  = "app"
          image = "nginx:1.27-alpine"

          resources {
            # Before the OOMKilled alert: memory limit was 256Mi.
            # Remediation: limit doubled to 512Mi; request raised proportionally.
            requests = {
              memory = "256Mi"
              cpu    = "100m"
            }
            limits = {
              memory = "512Mi"
              cpu    = "500m"
            }
          }

          port {
            container_port = 80
          }
        }
      }
    }
  }

  # Prevent Terraform from re-creating the deployment on every plan run
  # when the live replica count has been adjusted by an HPA.
  lifecycle {
    ignore_changes = [spec[0].replicas]
  }
}
