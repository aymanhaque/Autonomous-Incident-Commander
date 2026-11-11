import io
import re

import hcl2

# -----------------------------------------
# High-Risk Resource Catalog
# -----------------------------------------
HIGH_RISK_RESOURCE_TYPES = {
    # Networking
    "google_compute_network", "google_compute_subnetwork", "google_compute_firewall",
    "google_compute_router", "google_compute_forwarding_rule",
    "aws_vpc", "aws_subnet", "aws_security_group", "aws_route_table",
    "kubernetes_network_policy",
    # IAM / RBAC
    "google_project_iam_binding", "google_project_iam_member",
    "google_service_account_iam_binding",
    "aws_iam_role", "aws_iam_policy", "aws_iam_role_policy_attachment",
    "kubernetes_cluster_role_binding", "kubernetes_role_binding",
    # Databases
    "google_sql_database_instance", "aws_rds_instance", "aws_dynamodb_table",
    # Cluster-level
    "google_container_cluster", "aws_eks_cluster",
}

# -----------------------------------------
# Medium-Risk Resource Catalog
# -----------------------------------------
MEDIUM_RISK_RESOURCE_TYPES = {
    "kubernetes_deployment", "kubernetes_stateful_set", "kubernetes_daemon_set",
    "kubernetes_horizontal_pod_autoscaler", "kubernetes_pod_disruption_budget",
    "kubernetes_config_map", "kubernetes_secret", "kubernetes_service",
    "google_container_node_pool",
    "helm_release",
}


# -----------------------------------------
# Blast Radius Classifier
# -----------------------------------------
_SEVERITY_FLOOR = {
    "critical": "High",
    "warning": "Medium",
}

_LEVEL_ORDER = {"Low": 0, "Medium": 1, "High": 2}


def _max_level(a: str, b: str) -> str:
    return a if _LEVEL_ORDER.get(a, 0) >= _LEVEL_ORDER.get(b, 0) else b


def classify(terraform_plan: str, alert: dict | None = None) -> tuple[str, str]:
    """Return (risk_level, reason). risk_level is 'Low', 'Medium', or 'High'."""
    severity = (alert or {}).get("severity", "").lower()
    floor_level = _SEVERITY_FLOOR.get(severity)

    if not terraform_plan:
        level = _max_level("Low", floor_level) if floor_level else "Low"
        return level, "Empty plan"

    # Special-case text patterns before parsing — quick and provider-agnostic
    if re.search(r"replicas\s*=\s*0\b", terraform_plan):
        return "High", "Plan scales replicas to 0"

    if re.search(r"deletion_protection\s*=\s*false", terraform_plan):
        return "High", "Plan disables deletion protection"

    try:
        parsed = hcl2.load(io.StringIO(terraform_plan))
    except Exception:
        level = _max_level("Medium", floor_level) if floor_level else "Medium"
        return level, "Could not parse HCL — defaulting to Medium"

    resource_types = {
        rtype.strip('"')
        for block in parsed.get("resource", [])
        for rtype in block.keys()
    }

    high_matches = resource_types & HIGH_RISK_RESOURCE_TYPES
    if high_matches:
        return "High", f"Modifies high-risk resource types: {', '.join(sorted(high_matches))}"

    medium_matches = resource_types & MEDIUM_RISK_RESOURCE_TYPES
    if medium_matches:
        level = _max_level("Medium", floor_level) if floor_level else "Medium"
        return level, f"Modifies medium-risk resource types: {', '.join(sorted(medium_matches))}"

    if floor_level:
        return floor_level, f"Alert severity '{severity}' floors risk at {floor_level}"

    return "Low", "Plan makes low-blast-radius changes only"
