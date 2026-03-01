"""
Streamlit frontend for the Doctor Appointment Platform.

Connects to the platform API with session tracking,
multi-tenant support, and per-user memory management.
"""

import uuid
import streamlit as st
import requests
from utils.config import get_api_base_url

API_BASE = get_api_base_url()
API_URL = f"{API_BASE}/execute"
HEALTH_URL = f"{API_BASE}/health"
METRICS_URL = f"{API_BASE}/platform/metrics"
MEMORY_URL = f"{API_BASE}/platform/memory"

st.set_page_config(
    page_title="Doctor Appointment Platform",
    page_icon="🩺",
    layout="centered",
)

# ── Session state ────────────────────────────────────────────────

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# ── Sidebar: platform status ────────────────────────────────────

with st.sidebar:
    st.header("Platform Status")
    try:
        health = requests.get(HEALTH_URL, timeout=5).json()
        env = health.get("environment", "unknown")
        cb_state = health.get("circuit_breaker", {}).get("state", "unknown")
        tracing = health.get("tracing_enabled", False)
        memory_status = health.get("memory", {})

        st.metric("Environment", env.upper())
        st.metric("Circuit Breaker", cb_state.upper())
        st.metric("Tracing", "ON" if tracing else "OFF")
        st.metric("Memory", "ON" if memory_status.get("enabled") else "OFF")
    except Exception:
        st.warning("Platform API unreachable")

    st.divider()
    st.subheader("Settings")
    tenant_id = st.text_input("Tenant ID", value="default")

    st.divider()
    st.caption(f"Session: {st.session_state.session_id[:8]}...")

# ── Main UI ──────────────────────────────────────────────────────

st.title("🩺 Doctor Appointment Platform")
st.caption("Enterprise AI-powered assistant for appointment booking, cancellation, rescheduling, and availability checks.")

user_id = st.text_input("Patient ID (7-8 digits)", "")
query = st.text_area(
    "Your request",
    placeholder="Example: Can you check if a dentist is available tomorrow at 10 AM?",
)

if st.button("Submit Query", type="primary"):
    if user_id and query.strip():
        if not user_id.isdigit() or not (7 <= len(user_id) <= 8):
            st.error("Patient ID must be a 7-8 digit number.")
            st.stop()
        try:
            with st.spinner("Processing with AI agents..."):
                response = requests.post(
                    API_URL,
                    json={
                        "messages": query.strip(),
                        "id_number": int(user_id),
                        "tenant_id": tenant_id,
                        "session_id": st.session_state.session_id,
                    },
                    headers={
                        "X-Tenant-ID": tenant_id,
                        "X-User-ID": user_id,
                    },
                    timeout=60,
                )

            if response.status_code == 200:
                payload = response.json()
                st.success("Response received")
                st.markdown(payload.get("response", "No response generated."))

                with st.expander("Execution Details"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.caption(f"Route: {payload.get('route', 'N/A')}")
                        st.caption(f"Request ID: {payload.get('request_id', 'N/A')}")
                    with col2:
                        resp_time = response.headers.get("X-Response-Time-Ms", "N/A")
                        st.caption(f"Response Time: {resp_time} ms")
                    if payload.get("reasoning"):
                        st.text(f"Reasoning: {payload['reasoning']}")
            else:
                detail = response.json().get("detail", "Could not process the request.")
                st.error(f"Error {response.status_code}: {detail}")
        except requests.Timeout:
            st.error("The request timed out. Please try again.")
        except requests.RequestException as exc:
            st.error(f"Network error: {exc}")
    else:
        st.warning("Please provide both patient ID and a query.")

# ── Metrics dashboard tab ────────────────────────────────────────

st.divider()

with st.expander("📊 Platform Metrics Dashboard"):
    try:
        metrics = requests.get(METRICS_URL, timeout=5).json()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Requests", metrics.get("total_requests", 0))
        with col2:
            st.metric("Total Tool Calls", metrics.get("total_tool_invocations", 0))

        if metrics.get("agents"):
            st.subheader("Agent Performance")
            for name, data in metrics["agents"].items():
                st.caption(
                    f"**{name}**: {data['total_calls']} calls | "
                    f"{data['success_rate']:.1%} success | "
                    f"avg {data['avg_duration_ms']:.0f}ms"
                )

        if metrics.get("tools"):
            st.subheader("Tool Performance")
            for name, data in metrics["tools"].items():
                st.caption(
                    f"**{name}**: {data['total_calls']} calls | "
                    f"{data['success_rate']:.1%} success | "
                    f"avg {data['avg_duration_ms']:.0f}ms"
                )
    except Exception:
        st.info("Metrics unavailable — API may not be running.")
