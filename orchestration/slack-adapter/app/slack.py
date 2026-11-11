"""Slack helpers: request-signature verification + Block Kit message building.

The signature check is the security boundary of this adapter: without it, anyone
who learns the /slack/interactions URL could POST a forged 'approve' and drive a
remediation. Slack signs every request; we verify HMAC-SHA256 over
'v0:{timestamp}:{raw_body}' with the app signing secret and reject stale requests
(replay protection). See https://api.slack.com/authentication/verifying-requests.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import httpx


def verify_slack_signature(
    *,
    signing_secret: str,
    timestamp: str,
    signature: str,
    raw_body: str,
    max_skew_s: int = 300,
) -> bool:
    """Return True only for a genuine, fresh Slack request. Fails closed."""
    if not signing_secret:
        return False  # not configured -> reject everything
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(time.time() - ts) > max_skew_s:
        return False  # replay / clock-skew guard
    basestring = f"v0:{timestamp}:{raw_body}".encode()
    expected = "v0=" + hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def build_approval_message(approval: dict[str, Any], channel: str) -> dict[str, Any]:
    """Block Kit message for one pending approval, with Approve/Deny buttons.

    The button ``value`` carries the approval_id and ``action_id`` carries the
    decision, so the interaction callback needs nothing else. High-risk approvals
    get a native Slack confirm dialog, mirroring the Web UI's second-confirm gate.
    """
    approval_id = approval["approval_id"]
    risk = approval.get("risk", "?")
    high = risk == "High"

    approve_btn: dict[str, Any] = {
        "type": "button",
        "text": {"type": "plain_text", "text": "Approve"},
        "style": "primary",
        "action_id": "approve",
        "value": approval_id,
    }
    if high:
        approve_btn["confirm"] = {
            "title": {"type": "plain_text", "text": "High-risk change"},
            "text": {"type": "mrkdwn", "text": "This fix is classified *High* risk. Apply it?"},
            "confirm": {"type": "plain_text", "text": "Apply"},
            "deny": {"type": "plain_text", "text": "Cancel"},
        }
    deny_btn = {
        "type": "button",
        "text": {"type": "plain_text", "text": "Deny"},
        "style": "danger",
        "action_id": "deny",
        "value": approval_id,
    }

    header = f"{'⚠ ' if high else ''}{risk} risk · {approval.get('incident_id', '')}"
    return {
        "channel": channel,
        "text": f"Approval needed: {approval.get('plan_summary', '')}",  # notification fallback
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": header}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{approval.get('plan_summary', '')}*\nalert: `{approval.get('alert_type', '')}`",
                },
            },
            {"type": "actions", "block_id": approval_id, "elements": [approve_btn, deny_btn]},
        ],
    }


async def post_message(client: httpx.AsyncClient, token: str, message: dict[str, Any]) -> dict[str, Any]:
    r = await client.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}"},
        json=message,
    )
    return r.json()


async def respond_via_url(client: httpx.AsyncClient, response_url: str, text: str) -> None:
    """Replace the original message text (e.g. '(approved by @tarik)')."""
    await client.post(response_url, json={"replace_original": True, "text": text})
