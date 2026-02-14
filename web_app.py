import streamlit as st
import requests
from utils.config import get_api_base_url

API_URL = f"{get_api_base_url()}/execute"

st.set_page_config(page_title="Doctor Appointment Assistant", page_icon="🩺", layout="centered")
st.title("🩺 Doctor Appointment Assistant")
st.caption("AI-powered assistant for appointment booking, cancellation, rescheduling, and availability checks.")

user_id = st.text_input("Patient ID (7-8 digits)", "")
query = st.text_area("Your request", placeholder="Example: Can you check if a dentist is available tomorrow at 10 AM?")

if st.button("Submit Query"):
    if user_id and query.strip():
        if not user_id.isdigit() or not (7 <= len(user_id) <= 8):
            st.error("Patient ID must be a 7-8 digit number.")
            st.stop()
        try:
            with st.spinner("Contacting assistant..."):
                response = requests.post(
                    API_URL,
                    json={"messages": query.strip(), "id_number": int(user_id)},
                    timeout=45,
                )

            if response.status_code == 200:
                payload = response.json()
                st.success("Response received")
                st.markdown(payload.get("response", "No response generated."))
                if payload.get("route"):
                    st.caption(f"Route: {payload['route']}")
            else:
                detail = response.json().get("detail", "Could not process the request.")
                st.error(f"Error {response.status_code}: {detail}")
        except requests.Timeout:
            st.error("The request timed out. Please try again.")
        except requests.RequestException as exc:
            st.error(f"Network error: {exc}")
    else:
        st.warning("Please provide both patient ID and a query.")
