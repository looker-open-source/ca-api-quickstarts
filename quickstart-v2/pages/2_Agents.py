import os

import google.auth
import streamlit as st
from dotenv import load_dotenv
from google.api_core import exceptions as google_exceptions
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import geminidataanalytics
from google.protobuf.field_mask_pb2 import FieldMask
from streamlit_cookies_manager import EncryptedCookieManager

from app_secrets import get_secret
from auth import Authenticator
from error_handling import handle_errors


@handle_errors
def agents_main():
    # --- PAGE CONFIG ---
    st.set_page_config(
        page_title="Agents",
        page_icon="🤖",
        layout="wide",
    )
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 0rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --- LOAD ENV VARS ---
    load_dotenv()

    # --- AUTHENTICATION SETUP ---
    cookies = EncryptedCookieManager(
        password=get_secret(
            os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT"),
            "EncryptedCookieManager-secret",
        )
    )
    if not cookies.ready():
        st.info("Setting up session, please wait...")
        st.stop()

    auth = Authenticator(cookies)
    auth.check_session()

    if not st.session_state.get("user_email"):
        auth.login_widget()
        st.stop()

    if (
        "auth_token_info" not in st.session_state
        or st.session_state["auth_token_info"] is None
    ):
        st.error("Login succeeded but token info missing; please re-authenticate.")
        st.stop()

    # --- REFRESH CREDENTIALS IF NEEDED ---
    creds = st.session_state.get("creds")
    if creds and creds.refresh_token:
        try:
            creds.refresh(GoogleAuthRequest())
            st.session_state["auth_token_info"]["access_token"] = creds.token
            st.session_state["auth_token_info"]["expiry"] = creds.expiry.isoformat()
            auth._save_token_to_firestore(
                st.session_state["user_email"],
                st.session_state["auth_token_info"],
            )
        except Exception as e:
            st.error(f"Could not refresh credentials: {e}")
            st.stop()

    # --- HEADER & USER INFO ---
    user_info = {
        "name": st.session_state["auth_token_info"]
        .get("id_token_claims", {})
        .get("name"),
        "email": st.session_state["auth_token_info"].get("email"),
        "picture": st.session_state["auth_token_info"]
        .get("id_token_claims", {})
        .get("picture"),
    }
    col1, col2 = st.columns([5, 1])
    with col1:
        st.header("Agent Management")
    with col2:
        with st.popover(f"👤 {user_info.get('name')}", use_container_width=True):
            if user_info.get("picture"):
                st.image(user_info["picture"], width=80)
            st.markdown(f"**{user_info.get('name')}**")
            st.caption(user_info.get("email"))
            st.divider()
            if st.button("Logout", use_container_width=True):
                auth._clear_token_from_firestore(st.session_state.get("user_email"))
                cookies["user_email"] = ""
                for k in ["user_email", "auth_token_info", "creds"]:
                    st.session_state.pop(k, None)
                st.rerun()

    # --- CLIENT SETUP ---
    data_agent_client = geminidataanalytics.DataAgentServiceClient(credentials=creds)

    # --- SIDEBAR SETTINGS ---
    @st.cache_data
    def get_default_project_id():
        try:
            _, project_id = google.auth.default()
            return project_id
        except Exception:
            return None

    st.sidebar.header("Settings")
    billing_project = st.sidebar.text_input(
        "GCP Billing Project ID",
        get_default_project_id(),
        key="billing_project",
    )
    if not billing_project:
        st.sidebar.error("Please enter your GCP Billing Project ID")
        st.stop()

    # --- MAIN UI: LIST AND SHOW ---
    st.subheader("List and Show Agent Details")
    if st.button("Fetch Agents"):
        with st.spinner("Fetching agents..."):
            try:
                req = geminidataanalytics.ListDataAgentsRequest(
                    parent=f"projects/{billing_project}/locations/global"
                )
                agents = list(data_agent_client.list_data_agents(request=req))
                if not agents:
                    st.info("No agents found for this project.")
                for ag in agents:
                    disp = ag.display_name or ag.name.split("/")[-1]
                    with st.expander(disp):
                        st.write(f"**Resource:** `{ag.name}`")
                        if ag.description:
                            st.write(f"**Description:** {ag.description}")
                        st.write(f"**Created:** {ag.create_time}")
                        st.write(f"**Updated:** {ag.update_time}")
            except google_exceptions.GoogleAPICallError as e:
                st.error(f"API error fetching agents: {e}")
            except Exception as e:
                st.error(f"Unexpected error: {e}")

    st.divider()

    # --- MAIN UI: UPDATE AGENT ---
    st.subheader("Update a Data Agent")
    agent_id_to_update = st.text_input(
        "Agent ID to update",
        key="update_agent_id",
        help="Enter the final part of the agent resource name (e.g., 'agent_20250729120000')",
    )
    new_description = st.text_area("New description", key="update_desc")
    if st.button("Update Agent Description"):
        if not agent_id_to_update or not new_description:
            st.warning("Please provide both an Agent ID and a new description.")
        else:
            try:
                path = data_agent_client.data_agent_path(
                    billing_project, "global", agent_id_to_update
                )
                agent = geminidataanalytics.DataAgent(
                    name=path, description=new_description
                )
                mask = FieldMask(paths=["description"])
                data_agent_client.update_data_agent(agent=agent, update_mask=mask)
                st.success(f"Agent '{agent_id_to_update}' updated successfully!")
            except google_exceptions.GoogleAPICallError as e:
                st.error(f"API error updating agent: {e}")
            except Exception as e:
                st.error(f"Unexpected error: {e}")


agents_main()
