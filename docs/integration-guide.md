# AIC Integration Guide — Route B (one page)

Any system that can make an HTTP POST can approve or deny an AIC remediation.
The Web UI (Route A) and every external tool (Route B) call the **exact same
endpoint** — there is no separate integration API to build.

```
POST {APPROVAL_API}/approvals/{approval_id}/decide
Authorization: Bearer <API_SERVICE_TOKEN>          # service auth (fail-closed in prod)
X-Actor: <who is deciding>                         # identity: header, never the body
Content-Type: application/json

{"decision": "approve" | "deny",
 "decision_channel": "slack" | "teams" | "pagerduty" | "curl" | "api",
 "decision_note": "optional free text"}
```

Semantics every integrator can rely on:

- **One decision wins.** The transition is transactional; a second decide (any
  channel) returns `409 Conflict`. Safe to wire to double-clickable buttons.
- **Identity is the `X-Actor` header.** The body has no identity field, so a
  caller cannot forge who decided. In production a gateway verifies the caller
  and stamps this header.
- **Every decision is audited** (immutable `audit_log` row, committed atomically
  with the status flip) and **resumes the paused n8n workflow** automatically.
- Pull the queue from `GET /approvals/pending` (no auth); render
  `plan_summary`, `risk`, `incident_id`. The n8n resume handle is never present.
- If the response carries a non-null `resume_warning`, the decision is saved but
  n8n may not have resumed — re-drive idempotently with
  `POST /approvals/{id}/resume`.

## curl (the reference integration)

```bash
curl -s -X POST "$APPROVAL_API/approvals/$ID/decide" \
  -H "Authorization: Bearer $API_SERVICE_TOKEN" \
  -H "X-Actor: tarik@example.com" \
  -H "Content-Type: application/json" \
  -d '{"decision":"approve","decision_channel":"curl","decision_note":"LGTM"}'
```

## Slack (interactive buttons)

Post each pending approval as a message with two Block Kit buttons whose `value`
carries the approval id. One tiny handler maps the interaction to the API:

```
Slack button payload            ->  AIC decide call
------------------------------      ------------------------------------------
actions[0].action_id             ->  "approve" | "deny"      (the decision)
actions[0].value                 ->  approval_id             (URL path)
user.username / user.id          ->  X-Actor: slack:U12345   (identity)
                                 ->  decision_channel: "slack"
```

Handler pseudo-code (works as a Slack app action endpoint, an n8n workflow, or
a 20-line Cloud Function):

```python
@app.post("/slack/interact")
def on_slack_action(payload):
    action = payload["actions"][0]
    httpx.post(
        f"{APPROVAL_API}/approvals/{action['value']}/decide",
        headers={"Authorization": f"Bearer {API_SERVICE_TOKEN}",
                 "X-Actor": f"slack:{payload['user']['id']}"},
        json={"decision": action["action_id"], "decision_channel": "slack"},
    )
    return {"text": "Decision recorded."}   # 409 -> "Someone already decided."
```

## Teams / PagerDuty / ServiceNow

Identical shape, different trigger:

- **Teams**: an Adaptive Card `Action.Http` POSTs the decide call directly;
  `decision_channel: "teams"`, `X-Actor: teams:<user>`.
- **PagerDuty**: a webhook on incident acknowledge/resolve maps to
  approve/deny; `X-Actor: pagerduty:auto` for unattended rules.
- **ServiceNow**: a Business Rule or Flow Action on change-approval calls the
  same endpoint; the change ticket id goes in `decision_note`.

**The takeaway:** integrating a new tool is one HTTP call plus two headers. No
AIC code changes, no new endpoints, and the audit trail records the channel and
actor for every path.
