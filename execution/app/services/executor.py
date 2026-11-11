import asyncio
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

SANDBOX_ROOT = Path("/tmp/tf_sandboxes")
_TF_TIMEOUT = 300  # seconds per terraform phase


def _run_cmd(cmd: list[str], cwd: Path, phase: str) -> dict:
    """Run a single terraform subprocess command, stream all output to the logger."""
    logger.info("[%s] $ %s", phase, " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_TF_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        msg = f"Command timed out after {_TF_TIMEOUT}s"
        logger.error("[%s] %s", phase, msg)
        return {"returncode": -1, "stdout": "", "stderr": msg}
    except FileNotFoundError:
        msg = "'tflocal' binary not found. Ensure terraform-local is installed and on PATH."
        logger.error("[%s] %s", phase, msg)
        return {"returncode": -1, "stdout": "", "stderr": msg}

    if result.stdout.strip():
        logger.info("[%s] stdout:\n%s", phase, result.stdout.rstrip())
    if result.stderr.strip():
        log_fn = logger.warning if result.returncode == 0 else logger.error
        log_fn("[%s] stderr:\n%s", phase, result.stderr.rstrip())

    logger.info("[%s] exit_code=%d", phase, result.returncode)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


class TerraformExecutor:
    """
    Orchestrates the full Terraform lifecycle (init → validate → apply → rollback)
    inside isolated per-incident sandboxes under /tmp/tf_sandboxes/.

    run_pipeline() and rollback() are synchronous; callers should offload them to
    a thread via asyncio.to_thread so the event loop stays free.
    """

    # ------------------------------------------------------------------
    # Public pipeline methods
    # ------------------------------------------------------------------

    def run_pipeline(self, incident_id: str, workspace_id: str, hcl: str) -> dict:
        """
        Phase 1 — ISOLATE:  provision sandbox, write remediation.tf
        Phase 2 — VALIDATE: terraform init + terraform validate (pre-deploy guardrail)
        Phase 3 — EXECUTE:  terraform apply -auto-approve
        Phase 4 — CLEANUP:  shutil.rmtree on failure; sandbox preserved on success
                            so that rollback() can run terraform destroy against it.

        NOTE: In production, configure a remote Terraform backend (S3/GCS) so
        state is stored externally and the sandbox can always be wiped here.
        """
        sandbox = SANDBOX_ROOT / f"incident_{incident_id}"
        pipeline_success = False

        logger.info(
            "=== TF Pipeline START | incident=%s workspace=%s sandbox=%s ===",
            incident_id,
            workspace_id,
            sandbox,
        )

        try:
            # ── ISOLATION ─────────────────────────────────────────────
            sandbox.mkdir(parents=True, exist_ok=True)
            (sandbox / "remediation.tf").write_text(hcl)
            logger.info("[ISOLATE] Sandbox provisioned; HCL written to %s/remediation.tf", sandbox)

            # ── INIT ──────────────────────────────────────────────────
            r = _run_cmd(
                ["tflocal", "init", "-input=false", "-no-color"],
                sandbox,
                "INIT",
            )
            if r["returncode"] != 0:
                logger.error("[INIT] Provider initialisation failed — aborting.")
                return {"success": False, "failed_phase": "init", **r}

            # ── VALIDATE ──────────────────────────────────────────────
            r = _run_cmd(["tflocal", "validate", "-no-color"], sandbox, "VALIDATE")
            if r["returncode"] != 0:
                logger.error("[VALIDATE] HCL syntax check failed — aborting.")
                return {"success": False, "failed_phase": "validate", **r}

            # ── APPLY ─────────────────────────────────────────────────
            r = _run_cmd(
                ["tflocal", "apply", "-auto-approve", "-input=false", "-no-color"],
                sandbox,
                "APPLY",
            )
            if r["returncode"] != 0:
                logger.error("[APPLY] Apply failed.")
                return {"success": False, "failed_phase": "apply", **r}

            pipeline_success = True
            logger.info("=== TF Pipeline COMPLETE | incident=%s ===", incident_id)
            return {"success": True, "failed_phase": None, **r}

        except Exception as exc:
            logger.exception("[PIPELINE] Unhandled exception | incident=%s", incident_id)
            return {
                "success": False,
                "failed_phase": "unknown",
                "error": str(exc),
                "stdout": "",
                "stderr": "",
            }

        finally:
            if not pipeline_success:
                # Always wipe on failure to guarantee isolation.
                logger.info("[CLEANUP] Failure path — wiping sandbox: %s", sandbox)
                shutil.rmtree(sandbox, ignore_errors=True)
                logger.info("[CLEANUP] Sandbox removed.")
            else:
                # On success, preserve the sandbox (and its .terraform/state) so
                # rollback() can run terraform destroy without re-downloading state.
                logger.info(
                    "[LIFECYCLE] Apply succeeded — sandbox preserved for rollback: %s",
                    sandbox,
                )

    def rollback(self, incident_id: str) -> dict:
        """
        Destroy all Terraform-managed resources for a completed incident.
        Requires the sandbox to still exist (i.e. apply() succeeded and the
        sandbox was preserved by run_pipeline). Always wipes the sandbox in finally.
        """
        sandbox = SANDBOX_ROOT / f"incident_{incident_id}"
        logger.info(
            "=== TF Rollback START | incident=%s sandbox=%s ===", incident_id, sandbox
        )

        if not sandbox.exists():
            msg = (
                f"Rollback aborted: no sandbox found for incident '{incident_id}'. "
                "The sandbox may have already been cleaned up or never existed."
            )
            logger.error("[ROLLBACK] %s", msg)
            return {"success": False, "failed_phase": "rollback", "stdout": "", "stderr": msg}

        try:
            r = _run_cmd(
                ["tflocal", "destroy", "-auto-approve", "-input=false", "-no-color"],
                sandbox,
                "ROLLBACK",
            )
            if r["returncode"] == 0:
                logger.info("=== TF Rollback COMPLETE | incident=%s ===", incident_id)
            else:
                logger.error("[ROLLBACK] Destroy failed | incident=%s", incident_id)
            return {
                "success": r["returncode"] == 0,
                "failed_phase": None if r["returncode"] == 0 else "destroy",
                **r,
            }

        except Exception as exc:
            logger.exception("[ROLLBACK] Unhandled exception | incident=%s", incident_id)
            return {
                "success": False,
                "failed_phase": "destroy",
                "error": str(exc),
                "stdout": "",
                "stderr": "",
            }

        finally:
            logger.info("[CLEANUP] Wiping sandbox after rollback: %s", sandbox)
            shutil.rmtree(sandbox, ignore_errors=True)
            logger.info("[CLEANUP] Sandbox removed.")

    async def validate_only(self, hcl: str) -> dict:
        """
        Lightweight pre-flight HCL check (no backend, no cluster touch).
        Used by the approval gate before a plan is written to Firestore.
        """
        sandbox = Path(tempfile.mkdtemp(prefix="aic-preflight-"))
        try:
            (sandbox / "remediation.tf").write_text(hcl)

            r = await asyncio.to_thread(
                _run_cmd,
                ["tflocal", "init", "-input=false", "-no-color", "-backend=false"],
                sandbox,
                "PREFLIGHT/INIT",
            )
            if r["returncode"] != 0:
                return {"success": False, "failed_phase": "init", **r}

            r = await asyncio.to_thread(
                _run_cmd,
                ["tflocal", "validate", "-no-color"],
                sandbox,
                "PREFLIGHT/VALIDATE",
            )
            return {
                "success": r["returncode"] == 0,
                "failed_phase": None if r["returncode"] == 0 else "validate",
                **r,
            }
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)


executor = TerraformExecutor()
