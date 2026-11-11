"""AIC Slack Route-B adapter.

Two halves, both talking to the SAME Approval API the Web UI and curl use:

  1. A background poller: every few seconds it GETs /approvals/pending and posts
     any new pending approval to a Slack channel as a message with Approve / Deny
     buttons (Block Kit). In-memory de-dupe by approval_id (resets on restart --
     fine for a demo; back it with the message ts store for production).

  2. POST /slack/interactions: Slack calls this when a button is clicked. We
     VERIFY the Slack signature (the security boundary), then decide via
     POST /approvals/{id}/decide with X-Actor=slack:<user> and channel=slack, and
     update the Slack message with the outcome.

Nothing here re-implements the decision logic -- it is a thin translator from a
Slack interaction to the one decide endpoint, which is the whole point of Route B.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from urllib.parse import parse_qs

import httpx
from fastapi import BackgroundTasks, FastAPI, Request, Response

from .config import get_settings
from .slack import (
    build_approval_message,
    post_message,
    respond_via_url,
    verify_slack_signature,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aic.slack_adapter")
settings = get_settings()

# approval_id -> slack message ts (in-memory de-dupe so we post each gate once)
_posted: dict[str, str] = {}


async def _poll_pending() -> None:
    async with httpx.AsyncClient(timeout=settings.http_timeout_s) as client:
        while True:
            try:
                r = await client.get(f"{settings.approval_api_url}/approvals/pending")
                if r.status_code == 200:
                    for approval in r.json().get("items", []):
                        aid = approval["approval_id"]
                        if aid in _posted:
                            continue
                        resp = await post_message(
                            client, settings.slack_bot_token,
                            build_approval_message(approval, settings.slack_channel_id),
                        )
                        if resp.get("ok"):
                            _posted[aid] = resp.get("ts", "1")
                            logger.info("posted approval %s to slack", aid)
                        else:
                            logger.warning("slack post failed for %s: %s", aid, resp.get("error"))
            except Exception as exc:  # never let the poller die
                logger.warning("poll error: %s", exc)
            await _sleep(settings.poll_interval_s)


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


async def _process_decision(decision: str, approval_id: str, actor: str, user_id: str, response_url: str | None) -> None:
    """Do the decide + Slack message update AFTER we've already 200'd Slack.

    Slack requires a response within 3s; the decide + n8n resume can take longer,
    so we ack immediately (in the route) and finish the work here.
    """
    headers = {"X-Actor": actor, "Content-Type": "application/json"}
    if settings.api_service_token:
        headers["Authorization"] = f"Bearer {settings.api_service_token}"
    async with httpx.AsyncClient(timeout=settings.http_timeout_s) as client:
        try:
            dr = await client.post(
                f"{settings.approval_api_url}/approvals/{approval_id}/decide",
                headers=headers,
                json={"decision": decision, "decision_channel": "slack"},
            )
        except httpx.HTTPError as exc:
            text = f":warning: Could not reach the Approval API: {exc}"
            dr = None
        if dr is not None:
            if dr.status_code == 200:
                verb = "approved" if decision == "approve" else "denied"
                text = f":white_check_mark: *{verb}* by <@{user_id}> — remediation {'resuming' if verb == 'approved' else 'aborted'}."
            elif dr.status_code == 409:
                text = ":information_source: Already decided by someone else."
            elif dr.status_code in (401, 403):
                text = ":warning: Adapter is not authorized to decide (check API_SERVICE_TOKEN)."
            else:
                text = f":warning: Decision failed (HTTP {dr.status_code})."
        if response_url:
            await respond_via_url(client, response_url, text)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    task = None
    if settings.configured:
        task = asyncio.create_task(_poll_pending())
        logger.info("slack poller started (interval=%ss)", settings.poll_interval_s)
    else:
        logger.warning(
            "SLACK_BOT_TOKEN / SLACK_SIGNING_SECRET / SLACK_CHANNEL_ID not all set; "
            "poller disabled. The /slack/interactions endpoint still runs."
        )
    yield
    if task:
        task.cancel()


app = FastAPI(title="AIC Slack Route-B Adapter", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "configured": settings.configured, "tracked": len(_posted)}


@app.post("/slack/interactions")
async def interactions(request: Request, bg: BackgroundTasks):
    raw = (await request.body()).decode()
    if not verify_slack_signature(
        signing_secret=settings.slack_signing_secret,
        timestamp=request.headers.get("X-Slack-Request-Timestamp", ""),
        signature=request.headers.get("X-Slack-Signature", ""),
        raw_body=raw,
    ):
        return Response(status_code=401, content="bad slack signature")

    try:
        payload = json.loads(parse_qs(raw).get("payload", ["{}"])[0])
        action = payload["actions"][0]
        decision = action["action_id"]          # 'approve' | 'deny'
        approval_id = action["value"]            # the approval id
        user = payload.get("user", {})
    except (KeyError, IndexError, ValueError):
        return Response(status_code=400, content="unrecognized interaction payload")

    if decision not in ("approve", "deny"):
        return Response(status_code=400, content="unknown action")

    user_id = user.get("id", "")
    actor = f"{settings.actor_prefix}:{user.get('username') or user_id or 'unknown'}"
    # Ack Slack within 3s; do the decide + message update in the background.
    bg.add_task(_process_decision, decision, approval_id, actor, user_id, payload.get("response_url"))
    return Response(status_code=200)
