"""Environment config for the Slack Route-B adapter."""

from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        # --- Slack app credentials (you create the app; drop these in .env) ----
        self.slack_bot_token = os.getenv("SLACK_BOT_TOKEN", "")          # xoxb-...
        self.slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET", "")
        self.slack_channel_id = os.getenv("SLACK_CHANNEL_ID", "")        # C0123...

        # --- Approval API (same one the UI and curl use) -----------------------
        self.approval_api_url = os.getenv(
            "APPROVAL_API_URL", "http://approval_api:8080"
        ).rstrip("/")
        self.api_service_token = os.getenv("API_SERVICE_TOKEN", "")

        # --- Behavior ----------------------------------------------------------
        self.poll_interval_s = float(os.getenv("SLACK_POLL_INTERVAL_S", "5"))
        self.actor_prefix = os.getenv("SLACK_ACTOR_PREFIX", "slack")
        self.http_timeout_s = float(os.getenv("HTTP_TIMEOUT_S", "10"))

    @property
    def configured(self) -> bool:
        """True only when the Slack app credentials are all present."""
        return bool(
            self.slack_bot_token and self.slack_signing_secret and self.slack_channel_id
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
