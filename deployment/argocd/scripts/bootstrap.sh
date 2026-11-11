#!/usr/bin/env bash
# One-time setup: installs ArgoCD, pre-creates secrets, and applies the root App of Apps.
# Run this once against a fresh cluster. After this, ArgoCD owns all future deploys.
#
# Usage (from repo root):
#   bash deployment/argocd/scripts/bootstrap.sh
#
# Requires: deployment/helm/aic-chart/secrets.values.yaml (gitignored, must exist locally)
#           yq (brew install yq)
set -euo pipefail

REPO_URL="https://github.com/AlexGandarilla/Autonomous-Incident-Commander-Project"
ARGOCD_VERSION="stable"

# ── 1. Install ArgoCD ────────────────────────────────────────────────────────
echo ">>> Installing ArgoCD..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd --server-side \
  -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"

echo ">>> Waiting for ArgoCD server to be ready..."
kubectl wait --for=condition=available deployment/argocd-server \
  -n argocd --timeout=180s

# ── 2. Pre-create aic namespace and aic-secrets ──────────────────────────────
SECRETS_FILE="deployment/helm/aic-chart/secrets.values.yaml"

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "ERROR: $SECRETS_FILE not found. Must exist locally (it is gitignored)."
  exit 1
fi

echo ">>> Creating aic namespace and secrets..."
kubectl create namespace aic --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic aic-secrets \
  -n aic \
  --from-literal=GEMINI_API_KEY="$(yq '.secrets.geminiApiKey' "$SECRETS_FILE")" \
  --from-literal=GOOGLE_API_KEY="$(yq '.secrets.geminiApiKey' "$SECRETS_FILE")" \
  --from-literal=API_SERVICE_TOKEN="$(yq '.secrets.apiServiceToken' "$SECRETS_FILE")" \
  --from-literal=N8N_ENCRYPTION_KEY="$(yq '.secrets.n8nEncryptionKey' "$SECRETS_FILE")" \
  --from-literal=FIRESTORE_SA_JSON="$(yq '.secrets.firestoreSaJson' "$SECRETS_FILE")" \
  --dry-run=client -o yaml | kubectl apply -f -

echo ">>> aic-secrets created/updated."

# Tell ArgoCD never to prune this secret — it is managed here, not by Helm.
kubectl annotate secret aic-secrets -n aic \
  argocd.argoproj.io/sync-options=Prune=false --overwrite

# ── 3. Apply the root App of Apps ────────────────────────────────────────────
echo ">>> Applying App of Apps..."
kubectl apply -f - <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: aic-apps
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: ${REPO_URL}
    targetRevision: k8sDeployment
    path: deployment/argocd/apps
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
EOF

# ── 4. Print access instructions ─────────────────────────────────────────────
echo ""
echo "✓ Bootstrap complete. ArgoCD is managing the cluster."
echo ""
echo "Access the ArgoCD UI:"
echo "  kubectl port-forward -n argocd svc/argocd-server 8080:443"
echo "  open https://localhost:8080  (user: admin)"
echo ""
echo "Initial admin password:"
echo "  kubectl -n argocd get secret argocd-initial-admin-secret \\"
echo "    -o jsonpath='{.data.password}' | base64 -d && echo"
echo ""
echo "Watch sync status:"
echo "  kubectl get applications -n argocd -w"
