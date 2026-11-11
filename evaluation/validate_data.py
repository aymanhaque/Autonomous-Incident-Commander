import json
import os
import sys

# ============================================================
# validate_data.py
# Elias Khan 
# 
# This script checks that all JSON alert files in test_data/
# are correctly formatted before we feed them to the AI agent.
# ============================================================

# Required fields every alert must have
REQUIRED_ALERT_FIELDS = ["alertname", "severity", "namespace"]
REQUIRED_TOP_FIELDS = ["receiver", "status", "alerts"]

def validate_alert_file(filepath):
    """
    Opens a single JSON alert file and checks it has
    all the required fields. Returns True if valid.
    """
    filename = os.path.basename(filepath)
    print(f"\n Checking {filename}...")

    # Step 1: Try to open and parse the JSON
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"  FAIL - Invalid JSON format: {e}")
        return False

    # Step 2: Check top level fields exist
    for field in REQUIRED_TOP_FIELDS:
        if field not in data:
            print(f"  FAIL - Missing required top-level field: '{field}'")
            return False

    # Step 3: Check alerts array is not empty
    if len(data["alerts"]) == 0:
        print(f"  FAIL - 'alerts' array is empty")
        return False

    # Step 4: Check each alert has required label fields
    for i, alert in enumerate(data["alerts"]):
        if "labels" not in alert:
            print(f"  FAIL - Alert {i} is missing 'labels'")
            return False
        
        if "annotations" not in alert:
            print(f"  FAIL - Alert {i} is missing 'annotations'")
            return False

        for field in REQUIRED_ALERT_FIELDS:
            if field not in alert["labels"]:
                print(f"  FAIL - Alert {i} labels missing required field: '{field}'")
                return False

        if "summary" not in alert["annotations"]:
            print(f"  FAIL - Alert {i} annotations missing 'summary'")
            return False

        if "description" not in alert["annotations"]:
            print(f"  FAIL - Alert {i} annotations missing 'description'")
            return False

    print(f"  PASS - {filename} is valid")
    return True


def run_validation():
    """
    Finds all JSON files in test_data/ and validates each one.
    Prints a summary report at the end.
    """
    # Find the test_data folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    test_data_dir = os.path.join(script_dir, "test_data")

    # Check test_data folder exists
    if not os.path.exists(test_data_dir):
        print(f"ERROR: test_data/ folder not found at {test_data_dir}")
        sys.exit(1)

    # Get all JSON files
    json_files = [f for f in os.listdir(test_data_dir) if f.endswith(".json")]

    if len(json_files) == 0:
        print("ERROR: No JSON files found in test_data/")
        sys.exit(1)

    print(f"Found {len(json_files)} alert files to validate...")
    print("=" * 50)

    # Validate each file
    passed = 0
    failed = 0
    failed_files = []

    for filename in json_files:
        filepath = os.path.join(test_data_dir, filename)
        result = validate_alert_file(filepath)
        if result:
            passed += 1
        else:
            failed += 1
            failed_files.append(filename)

    # Print summary
    print("\n" + "=" * 50)
    print(f"VALIDATION SUMMARY")
    print("=" * 50)
    print(f"Total files checked : {len(json_files)}")
    print(f"Passed              : {passed}")
    print(f"Failed              : {failed}")

    if failed == 0:
        print("\n ALL FILES VALID - Test data is ready to use!")
    else:
        print(f"\n FAILED FILES:")
        for f in failed_files:
            print(f"  - {f}")
        print("\nFix the above files before running the test harness.")

    return failed == 0


if __name__ == "__main__":
    run_validation()