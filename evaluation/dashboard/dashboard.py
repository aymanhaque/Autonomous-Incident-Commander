import streamlit as st
import os
from datetime import datetime, timedelta
from google.cloud import firestore

# ============================================================
# dashboard.py
# Elias Khan - AI Evaluation & Test Data Engineer
#
# Streamlit dashboard showing AIC agent performance metrics.
# Reads test results live from the Firestore emulator's
# `test_results` collection (written by test_runner.py).
#
# --- FIRESTORE EMULATOR SETUP (per Tarik) ---
# No service account / credentials needed. From the repo root:
#   docker compose --profile emulator up -d firestore
# Then set (before running `streamlit run dashboard.py`):
#   export FIRESTORE_EMULATOR_HOST=127.0.0.1:8080
#   export FIRESTORE_PROJECT_ID=aic-local
# ============================================================

st.set_page_config(
    page_title="AIC Evaluation Dashboard",
    page_icon="🤖",
    layout="wide"
)

FIRESTORE_PROJECT_ID = os.environ.get("FIRESTORE_PROJECT_ID", "aic-local")
FIRESTORE_EMULATOR_HOST = os.environ.get("FIRESTORE_EMULATOR_HOST")
TEST_RESULTS_COLLECTION = "test_results"

MOCK_RESULTS = [
    {"filename": "oomkilled_pod.json",        "passed": False, "risk_score": "Low", "generation_time": 2.03, "risk_correct": False},
    {"filename": "gateway_timeout_504.json",  "passed": False, "risk_score": "Low", "generation_time": 2.04, "risk_correct": False},
    {"filename": "node_memory_pressure.json", "passed": False, "risk_score": "Low", "generation_time": 2.04, "risk_correct": False},
    {"filename": "cpu_throttling.json",       "passed": False, "risk_score": "Low", "generation_time": 2.11, "risk_correct": False},
    {"filename": "disk_pressure.json",        "passed": False, "risk_score": "Low", "generation_time": 2.04, "risk_correct": False},
    {"filename": "pod_crash_looping.json",    "passed": False, "risk_score": "Low", "generation_time": 2.06, "risk_correct": False},
    {"filename": "high_error_rate.json",      "passed": False, "risk_score": "Low", "generation_time": 2.04, "risk_correct": False},
]


@st.cache_resource
def get_firestore_client():
    if not FIRESTORE_EMULATOR_HOST:
        return None
    try:
        return firestore.Client(project=FIRESTORE_PROJECT_ID)
    except Exception:
        return None


# ── SIDEBAR ──
with st.sidebar:

    # Connection status
    st.subheader("Firestore Connection")
    if FIRESTORE_EMULATOR_HOST:
        st.success(f"Emulator: {FIRESTORE_EMULATOR_HOST}")
        st.caption(f"Project: {FIRESTORE_PROJECT_ID}")
    else:
        st.error("FIRESTORE_EMULATOR_HOST not set")

    if st.button("🔄 Refresh results"):
        get_firestore_client.clear()
        st.rerun()

    st.divider()

    # Date filter
    st.subheader("Filter Results")
    filter_option = st.radio(
        "View results from:",
        ["All Time", "Today", "Last 7 Days", "Pick a Date"]
    )

    selected_date = None
    if filter_option == "Pick a Date":
        selected_date = st.date_input(
            "Select date",
            value=datetime.now().date()
        )


def load_results():
    """
    Load test results from Firestore. Loads all results first
    then filters in Python to avoid timestamp type mismatch issues.
    Falls back to mock data if emulator not reachable or empty.
    """
    db = get_firestore_client()

    if db is None:
        st.warning(
            "Not connected to the Firestore emulator - showing mock data. "
            "Set FIRESTORE_EMULATOR_HOST (e.g. 127.0.0.1:8080) and "
            "FIRESTORE_PROJECT_ID (e.g. aic-local), and make sure "
            "`docker compose --profile emulator up -d firestore` is running.",
            icon="⚠️"
        )
        return MOCK_RESULTS

    try:
        docs = (
            db.collection(TEST_RESULTS_COLLECTION)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .stream()
        )
        all_results = [doc.to_dict() for doc in docs]

    except Exception as e:
        st.warning(
            f"Could not read from Firestore emulator ({e}) - showing mock data.",
            icon="⚠️"
        )
        return MOCK_RESULTS

    if not all_results:
        st.info(
            "Connected to Firestore emulator, but 'test_results' is empty. "
            "Run test_runner.py to populate it. Showing mock data for now."
        )
        return MOCK_RESULTS

    # Apply date filter in Python to avoid Firestore timestamp issues
    now = datetime.now()
    results = []

    for r in all_results:
        ts = r.get("timestamp")

        # Convert string timestamp to datetime if needed
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", ""))
            except Exception:
                ts = None

        # If no timestamp, always include the result
        if ts is None:
            results.append(r)
            continue

        # Get just the date part for comparison
        try:
            ts_date = ts.date() if hasattr(ts, "date") else None
        except Exception:
            ts_date = None

        if filter_option == "All Time":
            results.append(r)

        elif filter_option == "Today":
            if ts_date == now.date():
                results.append(r)

        elif filter_option == "Last 7 Days":
            if ts_date and ts_date >= (now - timedelta(days=7)).date():
                results.append(r)

        elif filter_option == "Pick a Date" and selected_date:
            if ts_date == selected_date:
                results.append(r)

    if not results and filter_option != "All Time":
        st.info(
            f"No results found for '{filter_option}'. "
            "Try a different date or select 'All Time'."
        )

    return results


# ── LOAD DATA ──
results = load_results()
total = len(results)
passed = sum(1 for r in results if r.get("passed"))
failed = total - passed
pass_rate = round((passed / total) * 100, 1) if total > 0 else 0
avg_time = round(
    sum(r.get("generation_time", 0) for r in results) / total, 2
) if total > 0 else 0

# ── HEADER ──
st.title("🤖 AIC Agent Evaluation Dashboard")
st.caption(
    f"Elias Khan — AI Evaluation & Test Data Engineer | "
    f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
    f"Showing: {filter_option}"
)
st.divider()

# ── TOP METRICS ──
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Tests", total)
col2.metric("Passed", passed, delta=f"{pass_rate}% pass rate")
col3.metric("Failed", failed)
col4.metric("Avg Generation Time", f"{avg_time}s")

st.divider()

# ── PASS RATE BAR ──
st.subheader("Overall Pass Rate")
st.progress(pass_rate / 100 if total > 0 else 0)
st.write(f"{passed} / {total} tests passing ({pass_rate}%)")

st.divider()

# ── TWO COLUMNS: Failures + Risk ──
left, right = st.columns(2)

with left:
    st.subheader("Failures by Alert Type")
    failed_tests = [r for r in results if not r.get("passed")]
    if failed_tests:
        for r in failed_tests:
            name = r.get("filename", "unknown").replace(".json", "").replace("_", " ").title()
            st.error(f"❌ {name}")
    else:
        if total > 0:
            st.success("All tests passing!")
        else:
            st.info("No results to display.")

with right:
    st.subheader("Risk Score Distribution")
    risk_counts = {"Low": 0, "Medium": 0, "High": 0, "Unknown": 0}
    for r in results:
        score = r.get("risk_score", "Unknown")
        if score in risk_counts:
            risk_counts[score] += 1
        else:
            risk_counts["Unknown"] += 1

    for score, count in risk_counts.items():
        if count > 0:
            color = {"Low": "🟢", "Medium": "🟡", "High": "🔴", "Unknown": "⚪"}
            st.write(f"{color[score]} **{score}**: {count} alerts")

st.divider()

# ── DETAILED RESULTS TABLE ──
st.subheader("Detailed Test Results")
if total == 0:
    st.info("No results found for the selected time period.")
else:
    for r in results:
        name = r.get("filename", "unknown").replace(".json", "").replace("_", " ").title()
        status = "✅ PASS" if r.get("passed") else "❌ FAIL"
        risk = r.get("risk_score", "Unknown")
        time_taken = r.get("generation_time", 0)
        ts = r.get("timestamp")
        ts_str = ts.strftime("%Y-%m-%d %H:%M") if hasattr(ts, "strftime") else str(ts)
        st.write(f"{status} | **{name}** | Risk: `{risk}` | Time: `{time_taken}s` | `{ts_str}`")

st.divider()
st.caption(
    "Dashboard reads live from the Firestore emulator's `test_results` collection. "
    "Historical data is never deleted — use the date filter in the sidebar to narrow results. "
    "Run test_runner.py to generate new results, then hit Refresh."
)