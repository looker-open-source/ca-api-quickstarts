# === FILE: app.py (ADC-only) ===
import getpass
import os

import google.auth
import streamlit as st
from dotenv import load_dotenv
from google.auth.transport.requests import AuthorizedSession
from google.auth.transport.requests import Request as GoogleAuthRequest
from streamlit_extras.add_vertical_space import add_vertical_space

from app_secrets import get_secret
from error_handling import handle_errors, handle_streamlit_exception


def get_adc_credentials(scopes=None):
    creds, project = google.auth.default(scopes=scopes)
    if not creds.valid:
        creds.refresh(GoogleAuthRequest())
    return creds, (os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or project)


@handle_errors
def main_part_one():
    st.set_page_config(
        page_title="Conversational Analytics API",
        page_icon="🗣️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .block-container { padding-top: 0rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    load_dotenv()

    SCOPES = [
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/bigquery",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/drive",
    ]
    creds, project_id = get_adc_credentials(scopes=SCOPES)

    st.session_state["adc_credentials"] = creds
    st.session_state["gcp_project_id"] = project_id
    st.session_state["authorized_session"] = AuthorizedSession(creds)

    principal = getattr(creds, "service_account_email", None) or getattr(creds, "quota_project_id", None) or "ADC principal"
    col1, col2 = st.columns([5, 1])
    with col1:
        add_vertical_space(3)
        st.title("Welcome to the Conversational Analytics API")
        st.markdown(
            """
This application provides:

- **Chat with your BigQuery data**
- **Manage Data Agents**
- **Browse Conversation History**

Select a page from the sidebar to get started.
            """
        )

    with col2:
        os_user = getpass.getuser()
        if os_user:
            with st.popover(f"👤 {os_user}", use_container_width=True, help="Click here to logout."):
                st.markdown(f"**{os_user} authenticated with Application Default Credentials**")

    st.sidebar.title("Navigation")
    st.sidebar.info("Choose one: Chat with your data, Agents, Conversations")

    try:
        from google.cloud import bigquery
        bq = bigquery.Client(project=project_id, credentials=creds)

    except Exception as e:
        handle_streamlit_exception(e, context_name="Initialize BigQuery client")

if __name__ == "__main__":
    main_part_one()
