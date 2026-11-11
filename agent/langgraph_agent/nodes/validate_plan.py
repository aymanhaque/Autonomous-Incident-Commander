# -----------------------------------------
# HCL Validation Node
# -----------------------------------------
import io
import hcl2

def validate_plan(state: dict) -> dict:
    plan = state.get("terraform_plan", "")

    if not plan:
        return {"error": "No terraform plan to validate", "validation_passed": False}

    try:
        hcl2.load(io.StringIO(plan))
        return {"validation_passed": True}
    except Exception as e:
        return {"error": f"HCL syntax error: {e}", "validation_passed": False}
