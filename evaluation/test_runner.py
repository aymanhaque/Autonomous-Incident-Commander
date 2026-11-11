import json
import os
import time
import requests
import sys
from datetime import datetime

# ============================================================
# test_runner.py
# Elias Khan - AI Evaluation & Test Data Engineer
#
# This script loads each alert from test_data/, sends it to
# Jean-Pascal's LangGraph API, validates the response, and
# prints a full pass/fail report with accuracy metrics.
# ============================================================

# URL of Jean-Pascal's API
API_URL = "http://localhost:8001/generate-plan"

# Set to True to run without JP's API
MOCK_MODE = False

# Where your alert JSON files live
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DATA_DIR = os.path.join(SCRIPT_DIR, "test_data")

# Output file for GitHub Actions to read
RESULTS_OUTPUT_FILE = os.path.join(SCRIPT_DIR, "last_run_results.txt")

# Expected risk scores for each alert type
EXPECTED_RISK = {
    "oomkilled_pod.json":               "High",
    "gateway_timeout_504.json":         "High",
    "node_memory_pressure.json":        "Medium",
    "cpu_throttling.json":              "Medium",
    "disk_pressure.json":               "High",
    "pod_crash_looping.json":           "High",
    "high_error_rate.json":             "High",
    "high_cpu_usage.json":              "Medium",
    "pod_pending.json":                 "Medium",
    "service_unavailable.json":         "High",
    "memory_leak.json":                 "Medium",
    "network_latency.json":             "Medium",
    "replica_mismatch.json":            "High",
    "container_restart_limit.json":     "High",
    "persistent_volume_full.json":      "High",
    "ingress_error.json":               "High",
    "database_connection_failed.json":  "High",
    "deployment_rollout_stuck.json":    "Medium",
    "namespace_resource_quota.json":    "Medium",
    "liveness_probe_failed.json":       "High",
    "network_failure.json":             "High",
}


def load_alert(filepath):
    """Load a single alert JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


def call_api(alert_data):
    """
    Send the alert to JP's API and return the response.
    If MOCK_MODE is True, return a fake response instead.
    """
    if MOCK_MODE:
        import unittest.mock as mock
        fake_response = mock.Mock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "terraform_plan": 'resource "kubernetes_deployment" "fix" { metadata { name = "patched" } }',
            "risk_score": "High",
            "validation_passed": True,
            "risk_reason": "Modifies deployment replicas",
            "alert_name": alert_data["alerts"][0]["labels"].get("alertname", "unknown"),
            "error": None
        }
        time.sleep(0.5)
        return fake_response, 0.5

    payload = {"alerts": alert_data["alerts"]}
    start_time = time.time()
    response = requests.post(API_URL, json=payload, timeout=30)
    end_time = time.time()
    return response, round(end_time - start_time, 2)


def validate_response(response, filename):
    """
    Check the API response and return a dict of results.
    """
    results = {
        "passed": False,
        "risk_score": "Unknown",
        "validation_passed": False,
        "terraform_plan_generated": False,
        "risk_score_correct": False,
        "error": None,
        "failures": []
    }

    if response.status_code != 200:
        results["failures"].append(f"API returned status {response.status_code}")
        results["error"] = f"HTTP {response.status_code}"
        return results

    data = response.json()

    if data.get("error"):
        results["failures"].append(f"API error: {data['error']}")
        results["error"] = data["error"]

    terraform_plan = data.get("terraform_plan", "")
    if terraform_plan and len(terraform_plan) > 10:
        results["terraform_plan_generated"] = True
    else:
        results["failures"].append("No Terraform plan generated")

    if data.get("validation_passed") == True:
        results["validation_passed"] = True
    else:
        results["failures"].append("Terraform validation did not pass")

    risk_score = data.get("risk_score", "Unknown")
    results["risk_score"] = risk_score
    if risk_score not in ["Low", "Medium", "High"]:
        results["failures"].append(f"Invalid risk score: {risk_score}")

    expected = EXPECTED_RISK.get(filename)
    if expected:
        if risk_score == expected:
            results["risk_score_correct"] = True
        else:
            results["failures"].append(
                f"Risk score mismatch: got '{risk_score}' expected '{expected}'"
            )

    if len(results["failures"]) == 0:
        results["passed"] = True

    return results


def run_end_to_end_benchmark(alert_data, filename):
    """
    Measures latency at each stage of the pipeline.
    Agent stage is real, approval and execution are simulated
    until Tarik and Muhd's layers are fully integrated.
    """
    benchmark = {
        "filename": filename,
        "latency_agent": None,
        "latency_approval": None,
        "latency_total": None
    }

    t_start = time.time()

    try:
        response, gen_time = call_api(alert_data)
        benchmark["latency_agent"] = round(gen_time, 2)
    except Exception as e:
        print(f"  Benchmark failed at agent stage: {e}")
        return benchmark

    # Simulated approval delay until Tarik's API is integrated
    approval_delay = 2.0
    time.sleep(approval_delay)
    benchmark["latency_approval"] = approval_delay

    # Simulated execution delay until Muhd's layer is integrated
    execution_delay = 3.0
    time.sleep(execution_delay)

    total = round(time.time() - t_start, 2)
    benchmark["latency_total"] = total

    return benchmark


def calculate_accuracy(results_summary):
    """
    Calculates and prints accuracy metrics across all test results.
    Returns a formatted string for GitHub comment posting.
    """
    total = len(results_summary)
    if total == 0:
        return ""

    passed = sum(1 for r in results_summary if r["passed"])
    accuracy = round((passed / total) * 100, 1)
    risk_correct = sum(1 for r in results_summary if r.get("risk_correct"))
    risk_accuracy = round((risk_correct / total) * 100, 1)
    plan_generated = sum(1 for r in results_summary if r.get("terraform_plan_generated"))
    plan_rate = round((plan_generated / total) * 100, 1)
    avg_time = round(
        sum(r.get("generation_time", 0) for r in results_summary) / total, 2
    ) if total > 0 else 0

    # Common failure modes
    failure_types = {}
    for r in results_summary:
        if not r["passed"]:
            for failure in r.get("failures", []):
                key = failure[:60]
                failure_types[key] = failure_types.get(key, 0) + 1

    lines = []
    lines.append("=" * 60)
    lines.append("ACCURACY REPORT")
    lines.append("=" * 60)
    lines.append(f"Overall accuracy      : {accuracy}% ({passed}/{total} passed)")
    lines.append(f"Risk score accuracy   : {risk_accuracy}% ({risk_correct}/{total} correct)")
    lines.append(f"Plan generation rate  : {plan_rate}% ({plan_generated}/{total} generated)")
    lines.append(f"Avg generation time   : {avg_time}s")

    if failure_types:
        lines.append("\nCommon Failure Modes:")
        for failure, count in sorted(failure_types.items(), key=lambda x: -x[1]):
            lines.append(f"  {count}x - {failure}")
    else:
        lines.append("\nNo failures detected!")

    report = "\n".join(lines)
    print(report)
    return report


def save_results_for_github(results_summary, accuracy_report):
    """
    Saves a summary of results to a text file so GitHub Actions
    can read it and post it as a PR comment.
    """
    total = len(results_summary)
    passed = sum(1 for r in results_summary if r["passed"])
    failed = total - passed
    avg_time = round(
        sum(r.get("generation_time", 0) for r in results_summary) / total, 2
    ) if total > 0 else 0

    lines = []
    lines.append("## 🤖 AIC Test Harness Results")
    lines.append(f"**Run time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Mode:** {'Mock' if MOCK_MODE else 'Real API'}")
    lines.append("")
    lines.append("### Summary")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total Tests | {total} |")
    lines.append(f"| Passed | {passed} ✅ |")
    lines.append(f"| Failed | {failed} ❌ |")
    lines.append(f"| Pass Rate | {round((passed/total)*100, 1) if total > 0 else 0}% |")
    lines.append(f"| Avg Generation Time | {avg_time}s |")
    lines.append("")

    if failed > 0:
        lines.append("### Failed Tests")
        for r in results_summary:
            if not r["passed"]:
                lines.append(f"- ❌ `{r['filename']}` — {r.get('error', 'see logs')}")
        lines.append("")

    lines.append("### Risk Score Distribution")
    risk_counts = {"Low": 0, "Medium": 0, "High": 0, "Unknown": 0}
    for r in results_summary:
        score = r.get("risk_score", "Unknown")
        risk_counts[score] = risk_counts.get(score, 0) + 1
    for score, count in risk_counts.items():
        if count > 0:
            lines.append(f"- {score}: {count}")

    content = "\n".join(lines)

    with open(RESULTS_OUTPUT_FILE, "w") as f:
        f.write(content)

    print(f"\nResults saved to {RESULTS_OUTPUT_FILE} for GitHub Actions")
    return content


def test_network_resilience():
    """
    Simulates different network failure scenarios and checks
    how the test harness handles them gracefully.
    """
    print("\n" + "=" * 60)
    print("NETWORK RESILIENCE TESTS")
    print("=" * 60)

    # Test 1 - Wrong URL (simulates network down)
    print("\nTest 1: Unreachable host...")
    try:
        requests.post(
            "http://localhost:9999/generate-plan",
            json={"alerts": []},
            timeout=3
        )
    except requests.exceptions.ConnectionError:
        print("  PASS - ConnectionError caught correctly")
    except Exception as e:
        print(f"  INFO - {type(e).__name__}: {e}")

    # Test 2 - Force timeout
    print("\nTest 2: Simulated timeout...")
    try:
        requests.post(
            API_URL,
            json={"alerts": []},
            timeout=0.001
        )
    except requests.exceptions.Timeout:
        print("  PASS - Timeout caught correctly")
    except requests.exceptions.ConnectionError:
        print("  PASS - Connection refused (API not running)")
    except Exception as e:
        print(f"  INFO - {type(e).__name__}: {e}")

    print("\nNetwork resilience tests complete!")


def run_tests():
    """
    Main function - runs all tests and prints a full report.
    """
    json_files = sorted([
        f for f in os.listdir(TEST_DATA_DIR)
        if f.endswith(".json") and f != "README.md"
    ])

    if not json_files:
        print("ERROR: No JSON files found in test_data/")
        return

    print("=" * 60)
    print("AIC TEST HARNESS - Elias Khan")
    print(f"Running {len(json_files)} tests against: {API_URL}")
    print(f"Mode: {'MOCK' if MOCK_MODE else 'REAL API'}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results_summary = []
    total_passed = 0
    total_failed = 0
    total_time = 0

    for filename in json_files:
        filepath = os.path.join(TEST_DATA_DIR, filename)
        print(f"\nTesting: {filename}")
        print("-" * 40)

        try:
            alert_data = load_alert(filepath)
        except Exception as e:
            print(f"  ERROR loading file: {e}")
            total_failed += 1
            continue

        try:
            response, generation_time = call_api(alert_data)
            print(f"  Generation time : {generation_time}s")
        except requests.exceptions.ConnectionError:
            print(f"  ERROR: Could not connect to API at {API_URL}")
            print(f"  Is Jean-Pascal's API running?")
            total_failed += 1
            results_summary.append({
                "filename": filename,
                "passed": False,
                "risk_score": "Unknown",
                "generation_time": 0,
                "error": "Connection refused",
                "failures": ["Connection refused"],
                "terraform_plan_generated": False,
                "risk_correct": False
            })
            continue
        except requests.exceptions.Timeout:
            print(f"  ERROR: API timed out after 30 seconds")
            total_failed += 1
            continue

        result = validate_response(response, filename)
        result["filename"] = filename
        result["generation_time"] = generation_time
        results_summary.append(result)

        status = "PASS" if result["passed"] else "FAIL"
        print(f"  Status          : {status}")
        print(f"  Risk Score      : {result['risk_score']}")
        print(f"  Plan Generated  : {result['terraform_plan_generated']}")
        print(f"  Validation Pass : {result['validation_passed']}")
        print(f"  Risk Correct    : {result['risk_score_correct']}")

        if result["failures"]:
            print(f"  Failures:")
            for f in result["failures"]:
                print(f"    - {f}")

        if result["passed"]:
            total_passed += 1
        else:
            total_failed += 1

        total_time += generation_time

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    print(f"Total tests         : {len(json_files)}")
    print(f"Passed              : {total_passed}")
    print(f"Failed              : {total_failed}")
    if results_summary:
        avg_time = round(total_time / len(results_summary), 2)
        print(f"Avg generation time : {avg_time}s")

    failed = [r for r in results_summary if not r["passed"]]
    if failed:
        print(f"\nFailed Tests:")
        for r in failed:
            print(f"  - {r['filename']} ({r.get('error', 'see above')})")

    print(f"\nRisk Score Breakdown:")
    for score in ["Low", "Medium", "High", "Unknown"]:
        count = sum(1 for r in results_summary if r["risk_score"] == score)
        if count > 0:
            print(f"  {score}: {count}")

    if total_failed == 0:
        print("\nALL TESTS PASSED!")
    else:
        print(f"\n{total_failed} TEST(S) FAILED - check above for details")

    print("=" * 60)

    # Accuracy report
    accuracy_report = calculate_accuracy(results_summary)

    # Save results for GitHub Actions
    save_results_for_github(results_summary, accuracy_report)

    return results_summary


if __name__ == "__main__":
    if "--network" in sys.argv:
        test_network_resilience()
    elif "--benchmark" in sys.argv:
        print("Running end-to-end benchmark on first alert...")
        files = [f for f in os.listdir(TEST_DATA_DIR) if f.endswith(".json")]
        if files:
            data = load_alert(os.path.join(TEST_DATA_DIR, files[0]))
            result = run_end_to_end_benchmark(data, files[0])
            print(f"\nBenchmark Results:")
            print(f"  Agent latency    : {result['latency_agent']}s")
            print(f"  Approval latency : {result['latency_approval']}s (simulated)")
            print(f"  Total latency    : {result['latency_total']}s")
    else:
        run_tests()
        test_network_resilience()