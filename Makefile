TERRAFORM_DIR   := deployment/terraform
HELM_DIR        := deployment/helm/aic-chart
ARGOCD_DIR      := deployment/argocd
SECRETS_FILE    := deployment/helm/aic-chart/secrets.values.yaml
CLUSTER_NAME    := aic-staging
AWS_REGION      := us-east-1
NAMESPACE       := aic

.PHONY: \
	# Infrastructure
	tf-init tf-plan tf-apply tf-destroy \
	# Cluster access
	kubeconfig \
	# Secret management
	secrets-create secrets-update \
	# ArgoCD bootstrap & management
	argocd-bootstrap argocd-sync argocd-status argocd-password argocd-ui \
	# Helm (direct deploy, no ArgoCD)
	helm-deploy helm-diff helm-uninstall \
	# Observability
	status logs \
	# Local dev
	build up down \
	# CI / evaluation
	test eval lint

##
## ── Infrastructure ─────────────────────────────────────────────────────────────
##

# Initialise Terraform backend and download providers
tf-init:
	terraform -chdir=$(TERRAFORM_DIR) init

# Preview what Terraform will change (no writes)
tf-plan:
	terraform -chdir=$(TERRAFORM_DIR) plan

# Provision VPC + EKS cluster (creates cluster, takes ~15 min)
tf-apply:
	terraform -chdir=$(TERRAFORM_DIR) apply

# Tear down all Terraform-managed AWS resources
tf-destroy:
	@echo "WARNING: this will destroy the EKS cluster and VPC."
	@read -p "Type 'yes' to confirm: " ans && [ "$$ans" = "yes" ]
	terraform -chdir=$(TERRAFORM_DIR) destroy

##
## ── Cluster access ─────────────────────────────────────────────────────────────
##

# Point kubectl at the staging EKS cluster
kubeconfig:
	aws eks update-kubeconfig --region $(AWS_REGION) --name $(CLUSTER_NAME)

##
## ── Secret management ──────────────────────────────────────────────────────────
##
# Requires: deployment/helm/aic-chart/secrets.values.yaml (gitignored)
# Requires: yq  (brew install yq)

# Create aic-secrets from secrets.values.yaml (idempotent — safe to re-run)
secrets-create:
	@if [ ! -f "$(SECRETS_FILE)" ]; then \
	  echo "ERROR: $(SECRETS_FILE) not found. Copy secrets.values.yaml.example and fill in values."; \
	  exit 1; \
	fi
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	kubectl create secret generic aic-secrets \
	  -n $(NAMESPACE) \
	  --from-literal=GEMINI_API_KEY="$$(yq '.secrets.geminiApiKey'     $(SECRETS_FILE))" \
	  --from-literal=GOOGLE_API_KEY="$$(yq '.secrets.geminiApiKey'     $(SECRETS_FILE))" \
	  --from-literal=API_SERVICE_TOKEN="$$(yq '.secrets.apiServiceToken' $(SECRETS_FILE))" \
	  --from-literal=N8N_ENCRYPTION_KEY="$$(yq '.secrets.n8nEncryptionKey' $(SECRETS_FILE))" \
	  --from-literal=FIRESTORE_SA_JSON="$$(yq '.secrets.firestoreSaJson'  $(SECRETS_FILE))" \
	  --dry-run=client -o yaml | kubectl apply -f -
	kubectl annotate secret aic-secrets -n $(NAMESPACE) \
	  argocd.argoproj.io/sync-options=Prune=false --overwrite
	@echo "aic-secrets created/updated in namespace $(NAMESPACE)"

# Re-apply updated secrets then restart all pods to pick up changes
secrets-update: secrets-create
	kubectl rollout restart deployment -n $(NAMESPACE)
	@echo "Pods restarting — watch with: kubectl rollout status deployment -n $(NAMESPACE)"

##
## ── ArgoCD bootstrap & management ─────────────────────────────────────────────
##

# One-time cluster bootstrap: installs ArgoCD, creates aic-secrets, applies App-of-Apps.
# Run once against a fresh cluster; ArgoCD owns all future deploys after this.
argocd-bootstrap:
	bash $(ARGOCD_DIR)/scripts/bootstrap.sh

# Manually trigger a sync of all ArgoCD apps (ArgoCD auto-syncs, but useful to force)
argocd-sync:
	argocd app sync aic-apps --cascade

# Show sync and health status of all AIC ArgoCD applications
argocd-status:
	argocd app list
	@echo ""
	kubectl get applications -n argocd

# Print the initial ArgoCD admin password
argocd-password:
	kubectl -n argocd get secret argocd-initial-admin-secret \
	  -o jsonpath='{.data.password}' | base64 -d && echo

# Port-forward the ArgoCD UI to https://localhost:8080
argocd-ui:
	kubectl port-forward -n argocd svc/argocd-server 8080:443

##
## ── Helm (direct deploy, bypasses ArgoCD) ──────────────────────────────────────
##
# Use for local testing or when ArgoCD is not installed.

# Install or upgrade the full AIC Helm chart directly
helm-deploy:
	helm upgrade --install aic $(HELM_DIR) \
	  -n $(NAMESPACE) --create-namespace \
	  -f $(HELM_DIR)/values.yaml

# Preview Helm changes without applying (requires helm-diff plugin)
helm-diff:
	helm diff upgrade aic $(HELM_DIR) \
	  -n $(NAMESPACE) \
	  -f $(HELM_DIR)/values.yaml

# Uninstall the Helm release (leaves namespace and secrets intact)
helm-uninstall:
	helm uninstall aic -n $(NAMESPACE)

##
## ── Observability ──────────────────────────────────────────────────────────────
##

# Show pod / deployment status across all AIC namespaces
status:
	@echo "=== $(NAMESPACE) ==="
	kubectl get pods,deployments,svc -n $(NAMESPACE)
	@echo ""
	@echo "=== aic-monitoring ==="
	-kubectl get pods,svc -n aic-monitoring
	@echo ""
	@echo "=== aic-redis ==="
	-kubectl get pods,svc -n aic-redis

# Tail logs for a service. Usage: make logs SVC=agent
logs:
	kubectl logs -n $(NAMESPACE) -l app=$(SVC) --tail=100 -f

##
## ── Local dev ──────────────────────────────────────────────────────────────────
##

build:
	docker compose build

up:
	docker compose up

down:
	docker compose down -v

##
## ── CI / evaluation ────────────────────────────────────────────────────────────
##

test:
	cd evaluation && pip install -q -r requirements.txt && python test_runner.py

eval:
	cd evaluation && streamlit run dashboard/app.py

lint:
	cd agent        && pip install -q ruff && ruff check .
	cd execution    && pip install -q ruff && ruff check .
	cd orchestration && pip install -q ruff && ruff check .
	cd evaluation   && pip install -q ruff && ruff check .
