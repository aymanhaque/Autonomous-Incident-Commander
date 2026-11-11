"""Environment-driven configuration for the Approval API.

Everything that differs between local-emulator dev and real-Firestore prod is
read from the environment here so the rest of the code never touches ``os.environ``
directly. Values mirror the repo-root ``.env.example`` and ``SCHEMA.md``
(project id ``aic-local`` on the emulator).

Verified emulator contract (firebase-admin, July 2026): when
``FIRESTORE_EMULATOR_HOST`` is set (host:port, NO ``http://`` scheme) the Admin
SDK automatically substitutes anonymous local credentials and routes to the
emulator -- no service-account JSON is used or needed. Setting the env var
BEFORE the client is created is what matters, so we surface it as a setting and
``firestore_repo`` guarantees ordering at import time.
"""

from __future__ import annotations

import os
from functools import lru_cache


def _split_csv(raw: str) -> list[str]:
    """Split a comma-separated env value into a clean, de-blanked list."""
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    """Flat settings object populated from the environment.

    Kept intentionally dependency-free (no pydantic-settings) so this module can
    be imported extremely early -- before the Firestore client is constructed --
    without dragging in heavier imports.
    """

    def __init__(self) -> None:
        # --- Firestore project / emulator -----------------------------------
        # In dev the emulator ignores the credential but still needs a project
        # id; SCHEMA.md pins it to ``aic-local``. ``GCLOUD_PROJECT`` and
        # ``FIRESTORE_PROJECT_ID`` are both honored (google-cloud-firestore reads
        # GCLOUD_PROJECT; our compose file sets FIRESTORE_PROJECT_ID).
        self.project_id: str = (
            os.getenv("FIRESTORE_PROJECT_ID")
            or os.getenv("GCLOUD_PROJECT")
            or "aic-local"
        )
        # host:port with NO protocol, e.g. ``firestore:8080`` (compose) or
        # ``127.0.0.1:8080`` (host). Empty/unset => talk to real Firestore.
        self.emulator_host: str | None = os.getenv("FIRESTORE_EMULATOR_HOST") or None

        # Optional explicit service-account path for prod. When the emulator host
        # is set this is ignored (the SDK uses anonymous local creds).
        self.credentials_path: str | None = os.getenv("FIRESTORE_CREDENTIALS_PATH") or None

        # --- Collections (kept configurable but default to SCHEMA.md names) ---
        self.approvals_collection: str = os.getenv("APPROVALS_COLLECTION", "approvals")
        self.audit_collection: str = os.getenv("AUDIT_COLLECTION", "audit_log")

        # --- Auth / trust boundary ------------------------------------------
        # The DECIDER identity is taken from this header, NOT from the request
        # body. In dev we simply read it; in prod a real gateway/JWT middleware
        # populates it after verifying the caller. See README trust-boundary note.
        self.actor_header: str = os.getenv("ACTOR_HEADER", "X-Actor")
        self.actor_fallback: str = os.getenv("ACTOR_FALLBACK", "unknown")

        # Shared service token gating the write endpoints (POST /approvals and
        # /decide). This is the API's OWN authentication -- distinct from the
        # X-Actor human-identity header. When unset in a NON-emulator deployment
        # the API fails CLOSED (503) so a prod deploy can never accidentally run
        # open. See ``main.require_service_auth``.
        self.service_token: str | None = os.getenv("API_SERVICE_TOKEN") or None

        # --- SSRF guard for the outbound n8n resume call --------------------
        # The n8n resume URL is CALLER-SUPPLIED at create time and later POSTed
        # server-side; without an allowlist it is a server-side request forgery
        # primitive (metadata endpoints, internal services, etc.). Only hosts in
        # this allowlist may be targeted. Defaults to the compose service name.
        self.n8n_resume_allowed_hosts: frozenset[str] = frozenset(
            _split_csv(os.getenv("N8N_RESUME_ALLOWED_HOSTS", "n8n,localhost,127.0.0.1"))
        )
        # HTTP methods the resume call may use (caller-supplied ``resume_method``
        # is constrained to this set).
        self.n8n_resume_allowed_methods: frozenset[str] = frozenset(
            m.upper() for m in _split_csv(os.getenv("N8N_RESUME_ALLOWED_METHODS", "POST,PUT"))
        )

        # --- CORS (least-privilege; empty by default => no CORS headers) -----
        # The browser Web UI (Route A) is cross-origin, so CORS will be needed.
        # We pin it to explicit origins from the env and NEVER wildcard with
        # credentials. Empty list (the default) means no CORS middleware is
        # installed at all -- the safe state.
        self.cors_allow_origins: list[str] = _split_csv(os.getenv("CORS_ALLOW_ORIGINS", ""))

        # --- Outbound n8n resume call ---------------------------------------
        # httpx default timeout is only 5s and easy to lose; we set it explicitly.
        self.n8n_resume_timeout_s: float = float(os.getenv("N8N_RESUME_TIMEOUT_S", "10.0"))

        # --- Misc ------------------------------------------------------------
        self.schema_version: int = int(os.getenv("SCHEMA_VERSION", "1"))
        # Cap for inline plans (~200KB per SCHEMA.md; Firestore doc cap is 1MiB).
        self.max_plan_inline_bytes: int = int(os.getenv("MAX_PLAN_INLINE_BYTES", str(200 * 1024)))
        # Cap for the (attacker-influenced) alert_payload map so a hostile create
        # cannot inflate the doc toward the 1MiB Firestore limit / waste memory.
        self.max_alert_payload_bytes: int = int(
            os.getenv("MAX_ALERT_PAYLOAD_BYTES", str(256 * 1024))
        )

    @property
    def using_emulator(self) -> bool:
        return self.emulator_host is not None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide singleton ``Settings`` instance."""
    return Settings()
