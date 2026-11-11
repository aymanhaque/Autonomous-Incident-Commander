# -----------------------------------------
# System Prompt
# -----------------------------------------
SUMMARY_SYSTEM_PROMPT = """You are an SRE assistant writing a short incident
summary for a human reviewer inside an approval dashboard. Given an alert and
the Terraform remediation plan already generated for it, write 2-3 plain
English sentences covering:
  1. What the alert means / what went wrong.
  2. What the proposed Terraform plan actually does to fix it.

Plain prose only -- no markdown, no headers, no bullet points. Do not repeat
the raw HCL back verbatim.
"""


# -----------------------------------------
# User Prompt Builder
# -----------------------------------------
def build_summary_prompt(alert: dict, terraform_plan: str) -> str:
    return f"""Alert details:
- Alert name: {alert.get("alertname", "Unknown")}
- Namespace:  {alert.get("namespace", "default")}
- Pod:        {alert.get("pod", "unknown")}
- Severity:   {alert.get("severity", "unknown")}
- Description: {alert.get("description", "(none provided)")}

Proposed Terraform remediation:
{terraform_plan}

Write the 2-3 sentence summary now."""
