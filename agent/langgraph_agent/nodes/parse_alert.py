# -----------------------------------------
# Alert Parsing Node
# -----------------------------------------
def parse_alert(state: dict) -> dict:
    payload = state.get("raw_alert", {})
    if not (alerts := payload.get("alerts", [])):
        return {"error": "No alerts found in webhook payload"}

    first = alerts[0]
    labels = first.get("labels", {})
    annotations = first.get("annotations", {})

    parsed = {
        "alertname": labels.get("alertname", "Unknown"),
        "namespace": labels.get("namespace", "default"),
        "pod": labels.get("pod"),
        "severity": labels.get("severity", "unknown"),
        "status": first.get("status", payload.get("status", "unknown")),
        "description": annotations.get("description")
        or annotations.get("summary", ""),
    }

    return {"alert": parsed}
