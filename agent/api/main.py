import hashlib
import json

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

from agent.langgraph_agent.graph import graph
from agent.api.schemas import PlanRequest, PlanResponse
from agent.langgraph_agent.nodes.parse_alert import parse_alert
from agent.langgraph_agent.nodes.validate_plan import validate_plan
from agent.langgraph_agent.nodes.classify_risk import classify_risk
from agent.langgraph_agent.nodes.generate_plan import _get_llm, _clean_hcl
from agent.langgraph_agent.nodes.summarize_remediation import summarize_remediation
from agent.prompts.plan_generation import SYSTEM_PROMPT, build_user_prompt


# -----------------------------------------
# App Initialization
# -----------------------------------------
app = FastAPI(title="AIC LangGraph Agent", version="0.1.0")


def _plan_hash(terraform_plan: str) -> str:
    """sha256 of the exact plan bytes, prefixed per SCHEMA.md (``sha256:<hex>``).

    The approval API stores this verbatim as tamper-evidence, so it must be
    computed over the same string we return as ``terraform_plan``. An empty plan
    still yields a valid non-empty digest (satisfies the API's min_length=1).
    """
    digest = hashlib.sha256(terraform_plan.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# -----------------------------------------
# Routes
# -----------------------------------------
@app.get("/health")
def health():
    """Simple liveness check — handy for Docker/K8s and for Ayman's setup."""
    return {"status": "ok"}


@app.post("/generate-plan", response_model=PlanResponse)
async def generate_plan_endpoint(body: PlanRequest):
    """
    Accepts a raw Prometheus/Alertmanager webhook payload, runs it through
    the agent graph, and returns the generated plan + risk score.
    """
    result = graph.invoke({"raw_alert": body.model_dump()})

    terraform_plan = result.get("terraform_plan", "")

    return PlanResponse(
        terraform_plan=terraform_plan,
        plan_hash=_plan_hash(terraform_plan),
        remediation_summary=result.get("remediation_summary"),
        risk_score=result.get("risk_score", "Unknown"),
        validation_passed=result.get("validation_passed", False),
        risk_reason=result.get("risk_reason"),
        alert_name=result.get("alert", {}).get("alertname"),
        error=result.get("error"),
    )


@app.post("/generate-plan/stream")
async def generate_plan_stream(body: PlanRequest):
    """
    Same pipeline as /generate-plan but streams progress as SSE events so the
    UI can show HCL tokens appearing in real time.

    Event shapes (all sent as `data: <json>\\n\\n`):
      alert_parsed  — { alertname, namespace, pod?, severity }
      token         — { content: str }   one per LLM output token
      plan_complete — { plan: str, plan_hash: str }  full cleaned HCL + sha256:<hex>
      summary       — { content: str }    Gemini's plain-English remediation summary
      validation    — { passed: bool }
      risk          — { score: str, reason: str }
      error         — { message: str }
      done          — {}                  always the final event
    """

    def _emit(event_type: str, data: dict) -> str:
        return f"data: {json.dumps({'type': event_type, 'data': data})}\n\n"

    async def event_stream():
        try:
            # ── 1. Parse alert ────────────────────────────────────────
            parsed = parse_alert({"raw_alert": body.model_dump()})
            if "error" in parsed and not parsed.get("alert"):
                yield _emit("error", {"message": parsed["error"]})
                return

            alert = parsed.get("alert", {})
            yield _emit("alert_parsed", alert)

            # ── 2. Stream LLM tokens ──────────────────────────────────
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=build_user_prompt(alert)),
            ]

            full_content = ""
            async for chunk in _get_llm().astream(messages):
                if chunk.content:
                    full_content += chunk.content
                    yield _emit("token", {"content": chunk.content})

            clean_plan = _clean_hcl(full_content)

            if not clean_plan:
                # The model occasionally returns a genuinely empty completion (safety
                # filtering, a blank candidate, etc). Retry once before giving up —
                # silently continuing with an empty plan would let validation and risk
                # classification "succeed" on nothing and save a hollow approval.
                full_content = ""
                async for chunk in _get_llm().astream(messages):
                    if chunk.content:
                        full_content += chunk.content
                        yield _emit("token", {"content": chunk.content})
                clean_plan = _clean_hcl(full_content)

            if not clean_plan:
                yield _emit("error", {"message": "Agent returned an empty Terraform plan — please try again."})
                return

            yield _emit("plan_complete", {"plan": clean_plan, "plan_hash": _plan_hash(clean_plan)})

            # ── 3. Summarize what the alert means + what the plan does ─
            summarized = summarize_remediation({"alert": alert, "terraform_plan": clean_plan})
            yield _emit("summary", {"content": summarized.get("remediation_summary", "")})

            # ── 4. Validate HCL ───────────────────────────────────────
            validated = validate_plan({"terraform_plan": clean_plan})
            yield _emit("validation", {"passed": validated.get("validation_passed", False)})

            # ── 5. Classify risk ──────────────────────────────────────
            classified = classify_risk({"terraform_plan": clean_plan, "alert": alert})
            yield _emit("risk", {
                "score": classified.get("risk_score", "Unknown"),
                "reason": classified.get("risk_reason", ""),
            })

        except Exception as exc:
            yield _emit("error", {"message": str(exc)})
        finally:
            yield _emit("done", {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
