import os
import re
from collections import defaultdict
from google.cloud import firestore

# ============================================================
# failure_analysis.py
# Elias Khan - AI Evaluation & Test Data Engineer
#
# Reads every test_results doc from the Firestore emulator,
# keeps only the MOST RECENT run per alert file (so re-runs
# don't double-count old failures), and groups failures by:
#   1. Failure category (e.g. "terraform validation failed",
#      "risk score too low", "no plan generated")
#   2. Alert file / alert type
#
# Prints a report, and also writes a markdown summary to
# failure_report.md so it can be pasted straight into the
# 1-page AI Performance Report.
#
# --- FIRESTORE EMULATOR SETUP (per Tarik) ---
# export FIRESTORE_EMULATOR_HOST=127.0.0.1:8080
# export FIRESTORE_PROJECT_ID=aic-local
# ============================================================

FIRESTORE_PROJECT_ID = os.environ.get("FIRESTORE_PROJECT_ID", "aic-local")
FIRESTORE_EMULATOR_HOST = os.environ.get("FIRESTORE_EMULATOR_HOST")
TEST_RESULTS_COLLECTION = "test_results"
OUTPUT_MD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "failure_report.md")

# Ordered list of (regex pattern, category label).
# Checked top to bottom - first match wins. Add new patterns here
# as new failure strings show up in validate_response().
FAILURE_CATEGORIES = [
    (r"^API returned status \d+$",                    "HTTP error from API"),
    (r"^API error: Hard stop",                         "Unexpected hard stop (High risk not expected)"),
    (r"^API error:",                                   "Other API error"),
    (r"^No Terraform plan generated$",                 "No Terraform plan generated"),
    (r"^Terraform validation did not pass$",            "Terraform validation failed"),
    (r"^Invalid risk score:",                           "Invalid / missing risk score"),
    (r"^Risk score below threshold:",                   "Risk score too low (under-classified)"),
    (r"^Cannot compare risk score",                     "Risk score comparison error"),
]


def categorize_failure(failure_text):
    """Map a raw failure string to a human-readable category."""
    for pattern, label in FAILURE_CATEGORIES:
        if re.search(pattern, failure_text):
            return label
    return "Uncategorized: " + failure_text


def get_firestore_client():
    if not FIRESTORE_EMULATOR_HOST:
        print("ERROR: FIRESTORE_EMULATOR_HOST is not set.")
        print("  export FIRESTORE_EMULATOR_HOST=127.0.0.1:8080")
        print("  export FIRESTORE_PROJECT_ID=aic-local")
        return None
    try:
        client = firestore.Client(project=FIRESTORE_PROJECT_ID)
        print(f"Connected to Firestore emulator at {FIRESTORE_EMULATOR_HOST} "
              f"(project={FIRESTORE_PROJECT_ID})")
        return client
    except Exception as e:
        print(f"ERROR: Could not create Firestore client: {e}")
        return None


def fetch_latest_results(db):
    """
    Pull every doc from test_results and keep only the most recent
    run per filename (doc ids are '{filename}_{timestamp_ms}', and
    each doc also has an ISO 'timestamp' field written by test_runner.py).
    """
    docs = list(db.collection(TEST_RESULTS_COLLECTION).stream())
    if not docs:
        return {}

    latest_by_filename = {}
    for doc in docs:
        data = doc.to_dict()
        filename = data.get("filename")
        if not filename:
            continue
        timestamp = data.get("timestamp", "")
        existing = latest_by_filename.get(filename)
        if existing is None or timestamp > existing.get("timestamp", ""):
            latest_by_filename[filename] = data

    return latest_by_filename


def analyze(latest_by_filename):
    """
    Build:
      - category_counts: how many test cases hit each failure category
      - category_to_files: which alert files hit each category
      - file_failure_counts: total failure count per alert file
      - passed / failed / total summary
    """
    category_counts = defaultdict(int)
    category_to_files = defaultdict(set)
    file_failure_counts = defaultdict(int)

    total = len(latest_by_filename)
    passed = 0
    failed_files = []

    for filename, data in latest_by_filename.items():
        if data.get("passed"):
            passed += 1
            continue

        failed_files.append(filename)
        failures = data.get("failures", [])
        file_failure_counts[filename] = len(failures)

        if not failures:
            # e.g. connection refused / timeout entries with no "failures" list
            err = data.get("error", "Unknown error")
            category = f"Run-level error: {err}"
            category_counts[category] += 1
            category_to_files[category].add(filename)
            continue

        for f in failures:
            category = categorize_failure(f)
            category_counts[category] += 1
            category_to_files[category].add(filename)

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "failed_files": sorted(failed_files),
        "category_counts": dict(category_counts),
        "category_to_files": {k: sorted(v) for k, v in category_to_files.items()},
        "file_failure_counts": dict(file_failure_counts),
    }


def print_report(analysis):
    print("=" * 60)
    print("FAILURE MODE ANALYSIS - Elias Khan")
    print("=" * 60)
    print(f"Total alert files evaluated : {analysis['total']}")
    print(f"Passed                      : {analysis['passed']}")
    print(f"Failed                      : {analysis['failed']}")

    if not analysis["failed_files"]:
        print("\nNo failures found - nothing to categorize.")
        print("=" * 60)
        return

    print("\nFailure categories (most common first):")
    print("-" * 60)
    sorted_categories = sorted(
        analysis["category_counts"].items(), key=lambda x: x[1], reverse=True
    )
    for category, count in sorted_categories:
        files = analysis["category_to_files"][category]
        print(f"  [{count}x] {category}")
        print(f"        affected: {', '.join(files)}")

    print("\nFailures by alert file:")
    print("-" * 60)
    for filename in analysis["failed_files"]:
        count = analysis["file_failure_counts"].get(filename, 0)
        print(f"  {filename}: {count} failure(s)")

    print("=" * 60)


def write_markdown_report(analysis):
    lines = []
    lines.append("# Failure Mode Analysis\n")
    lines.append(f"- **Total alert files evaluated:** {analysis['total']}")
    lines.append(f"- **Passed:** {analysis['passed']}")
    lines.append(f"- **Failed:** {analysis['failed']}\n")

    if not analysis["failed_files"]:
        lines.append("No failures found in the most recent test run.\n")
    else:
        lines.append("## Failure categories\n")
        sorted_categories = sorted(
            analysis["category_counts"].items(), key=lambda x: x[1], reverse=True
        )
        lines.append("| Category | Count | Affected alert types |")
        lines.append("|---|---|---|")
        for category, count in sorted_categories:
            files = analysis["category_to_files"][category]
            clean_files = ", ".join(f.replace(".json", "") for f in files)
            lines.append(f"| {category} | {count} | {clean_files} |")

        lines.append("\n## Failures by alert file\n")
        lines.append("| Alert file | Failure count |")
        lines.append("|---|---|")
        for filename in analysis["failed_files"]:
            count = analysis["file_failure_counts"].get(filename, 0)
            lines.append(f"| {filename} | {count} |")

    with open(OUTPUT_MD_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nMarkdown summary written to: {OUTPUT_MD_PATH}")


def main():
    db = get_firestore_client()
    if db is None:
        return

    latest_by_filename = fetch_latest_results(db)
    if not latest_by_filename:
        print("No documents found in the 'test_results' collection. "
              "Run test_runner.py first.")
        return

    analysis = analyze(latest_by_filename)
    print_report(analysis)
    write_markdown_report(analysis)


if __name__ == "__main__":
    main()