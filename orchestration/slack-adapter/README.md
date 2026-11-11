# Slack Route-B adapter

Proof that Route B is real: this adapter posts each pending approval to Slack with
Approve / Deny buttons, and a button click calls the **exact same**
`POST /approvals/{id}/decide` endpoint the Web UI and curl use. Zero changes to the
Approval API — a new channel is just a thin translator.

```
Approval API  --GET /approvals/pending-->  adapter  --chat.postMessage-->  #channel
#channel  --button click-->  adapter (/slack/interactions, signature-verified)
adapter  --POST /decide (X-Actor: slack:<user>, channel: slack)-->  Approval API  --> n8n resumes
```

## What you plug in (5 minutes)

Everything else is built. You create a Slack app and drop three values in `.env`:

1. **Create a Slack app** at <https://api.slack.com/apps> → *From scratch*.
2. **Bot token scope** `chat:write` (OAuth & Permissions), install to the workspace,
   copy the **Bot User OAuth Token** (`xoxb-...`).
3. **Signing secret** from *Basic Information* → App Credentials.
4. **Interactivity**: turn it on and set the **Request URL** to your adapter's
   public `/slack/interactions` (for local dev, tunnel it: `ngrok http 8092`, then
   use `https://<id>.ngrok.io/slack/interactions`).
5. **Channel id**: invite the bot to a channel, copy the channel id (`C0…`).

```bash
# .env
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
SLACK_CHANNEL_ID=C0123ABC
# reuses the same APPROVAL_API_URL + API_SERVICE_TOKEN as the rest of the stack
```

## Run

```bash
# with the stack (opt-in profile; leaves the default `up` unchanged):
docker compose --profile slack up -d --build slack-adapter

# or standalone:
cd orchestration/slack-adapter
pip install -r requirements.txt
APPROVAL_API_URL=http://localhost:8090 uvicorn app.main:app --port 8092
```

`GET /healthz` reports `configured` (are the Slack creds present?) and how many
approvals are being tracked. If the Slack creds are missing, the poller stays off
but `/slack/interactions` still runs, so the security check is always testable.

## Security

- **Every interaction is signature-verified** (`app/slack.py`): HMAC-SHA256 over
  `v0:{timestamp}:{body}` with the signing secret, plus a 5-minute freshness
  window against replay. A forged or stale POST gets `401`. This is the boundary
  that stops anyone who learns the URL from forging an approval.
- **Identity is server-set**: the decide call sends `X-Actor: slack:<user>`, so
  the audit log records the real Slack user, never a body-supplied identity.
- The bot token and signing secret live in `.env` (gitignored), never in code.

## Notes

- The poller de-dupes in memory (resets on restart) — fine for the demo. For
  production, persist the `approval_id -> message ts` map and reconcile on boot.
- To push instead of poll, add an HTTP node to the n8n workflow that POSTs the new
  approval to a `/notify` endpoint; the poll approach needs no workflow change.
