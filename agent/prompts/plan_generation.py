# -----------------------------------------
# System Prompt
# -----------------------------------------
SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) assistant.
Your job is to read a Kubernetes/infrastructure alert and produce a Terraform
(HCL) plan that remediates it.

Rules you MUST follow:
- Output ONLY valid Terraform HCL. No explanations, no markdown code fences.
- Make the SMALLEST change that addresses the alert. Do not refactor unrelated
  infrastructure.
- Never delete resources or change networking unless the alert clearly requires
  it. Prefer adjusting resource limits, replica counts, or probes.
- Use the namespace and resource names provided in the alert.
- If you are unsure, produce the most conservative, low-blast-radius change.
"""


# -----------------------------------------
# User Prompt Builder
# -----------------------------------------
def build_user_prompt(alert: dict) -> str:
    return f"""An infrastructure alert has fired. Generate a Terraform plan to fix it.

Alert details:
- Alert name: {alert.get("alertname", "Unknown")}
- Namespace:  {alert.get("namespace", "default")}
- Pod:        {alert.get("pod", "unknown")}
- Severity:   {alert.get("severity", "unknown")}
- Status:     {alert.get("status", "unknown")}
- Description: {alert.get("description", "(none provided)")}

Return only the Terraform HCL needed to remediate this specific alert."""
