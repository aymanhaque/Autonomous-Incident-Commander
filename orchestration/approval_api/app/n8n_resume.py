"""Outbound n8n resume call.

After a decision is DURABLY recorded, the API POSTs to the stored
``n8n.resume_webhook_url`` to wake the paused workflow (the PUSH model in
SCHEMA.md). Critical failure-handling contract from the API spec:

  * The decision is ALREADY committed before we get here. If the resume call
    fails, we DO NOT roll anything back and DO NOT raise -- we return a warning
    string so the endpoint can respond success-with-warning. Corrupting the
    committed decision to reflect a transport blip would be worse than a missed
    resume (a poll-based watchdog / the /resume recovery endpoint re-drives
    missed resumes; see SCHEMA.md and README).
  * We DO NOT retry inside the request in a way that could double-resume: the
    resume URL is single-use per execution, so a retry that actually lands twice
    is a correctness bug. One attempt, then warn.

Defense in depth: the URL is already scheme/host-allowlisted at the model layer
(``models.N8nHandle``), and here we additionally disable redirect following so a
302 to an internal/metadata address cannot bypass that allowlist.

httpx exception handling verified July 2026: ``TimeoutException`` and
``HTTPStatusError`` are handled distinctly; ``RequestError`` is the broad base
for connect/transport failures. ``HTTPStatusError`` is raised only by
``raise_for_status()`` and is NOT a ``RequestError`` subclass.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from .config import get_settings

logger = logging.getLogger("aic.approval_api.n8n_resume")


async def resume_n8n(
    n8n_handle: dict[str, Any],
    *,
    approval_id: str,
    decision: str,
    decided_by: str,
) -> Optional[str]:
    """POST the decision to the n8n resume URL.

    Returns ``None`` on success, or a human-readable warning string if the
    resume attempt failed (the caller turns this into ``resume_warning`` in the
    response and logs it). NEVER raises for an upstream/transport failure.
    """
    settings = get_settings()
    url = n8n_handle.get("resume_webhook_url")
    method = (n8n_handle.get("resume_method") or "POST").upper()

    if not url:
        # Missing capability -- record it but don't fail the (already durable)
        # decision. This should be impossible given create-time validation.
        warning = "no resume_webhook_url on approval; n8n was not resumed"
        logger.error("%s (approval_id=%s)", warning, approval_id)
        return warning

    # The Wait node reads these off its output items as $json.body.<field>.
    body = {"approval_id": approval_id, "decision": decision, "decided_by": decided_by}

    try:
        # follow_redirects=False: a 302 to an internal/metadata host must not
        # bypass the model-layer host allowlist (SSRF defense in depth).
        async with httpx.AsyncClient(
            timeout=settings.n8n_resume_timeout_s, follow_redirects=False
        ) as client:
            # Single attempt only -- resume URLs are single-use; a retry that
            # lands could double-resume the workflow.
            resp = await client.request(method, url, json=body)
            resp.raise_for_status()
        logger.info("resumed n8n for approval_id=%s decision=%s", approval_id, decision)
        return None
    except httpx.TimeoutException:
        warning = "n8n resume timed out; decision recorded, workflow may not have resumed"
    except httpx.HTTPStatusError as exc:  # non-2xx from n8n (e.g. 404 not-waiting)
        warning = (
            f"n8n resume returned HTTP {exc.response.status_code}; decision recorded, "
            "workflow may not have resumed"
        )
    except httpx.RequestError:  # connect/transport failure
        warning = "n8n resume unreachable; decision recorded, workflow may not have resumed"

    logger.warning("%s (approval_id=%s)", warning, approval_id)
    return warning
