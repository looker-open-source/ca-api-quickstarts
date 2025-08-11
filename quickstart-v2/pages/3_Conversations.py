import os

import google.auth
import pandas as pd
import proto
import streamlit as st
from dotenv import load_dotenv
from google.api_core import exceptions as google_exceptions
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import geminidataanalytics
from google.protobuf.json_format import MessageToDict
from streamlit_cookies_manager import EncryptedCookieManager

from app_secrets import get_secret
from auth import Authenticator
from error_handling import handle_errors


@handle_errors
def conversations_main():
    # --- PAGE CONFIG ---
    st.set_page_config(
        page_title="Conversations",
        page_icon="📜",
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

    load_dotenv()

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

    # --- CLIENT SETUP ---
    client_agents = geminidataanalytics.DataAgentServiceClient(credentials=creds)
    client_chat = geminidataanalytics.DataChatServiceClient(credentials=creds)

    # --- HEADER & USER INFO ---
    user_info = {
        "email": st.session_state["auth_token_info"].get("email"),
        "name": st.session_state.get("auth_token_info", {})
        .get("id_token_claims", {})
        .get("name"),
        "picture": st.session_state.get("auth_token_info", {})
        .get("id_token_claims", {})
        .get("picture"),
    }
    col1, col2 = st.columns([5, 1])
    with col1:
        st.header("Conversation History")
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
        "GCP Billing Project ID", get_default_project_id(), key="billing_project"
    )
    if not billing_project:
        st.sidebar.error("Please enter your GCP Billing Project ID")
        st.stop()

    # --- LOAD AGENTS MAP & CONVERSATIONS ---
    SESSION_AGENTS_MAP = "agents_map"
    SESSION_CONVERSATIONS = "conversations"
    if SESSION_AGENTS_MAP not in st.session_state:
        st.session_state[SESSION_AGENTS_MAP] = {}
    if SESSION_CONVERSATIONS not in st.session_state:
        st.session_state[SESSION_CONVERSATIONS] = []

    # --- LOAD CONVERSATIONS ---
    if st.button("Load Conversations"):
        with st.spinner("Loading conversations..."):
            try:
                agents = list(
                    client_agents.list_data_agents(
                        parent=f"projects/{billing_project}/locations/global"
                    )
                )
                st.session_state[SESSION_AGENTS_MAP] = {a.name: a for a in agents}
                convos = list(
                    client_chat.list_conversations(
                        parent=f"projects/{billing_project}/locations/global"
                    )
                )
                st.session_state[SESSION_CONVERSATIONS] = convos
                if not convos:
                    st.info("No conversations found.")
            except google_exceptions.GoogleAPICallError as e:
                st.error(f"API error loading: {e}")
            except Exception as e:
                st.error(f"Unexpected error: {e}")

    # --- DISPLAY CONVERSATIONS & MESSAGES ---
    for conv in st.session_state[SESSION_CONVERSATIONS]:
        title = conv.name.split("/")[-1]
        last_used = conv.last_used_time.strftime("%Y-%m-%d %H:%M:%S")
        with st.expander(f"Conversation: `{title}` (Last Used: {last_used})"):
            if st.button(f"View Messages for {title}", key=f"view_{title}"):
                with st.spinner(f"Fetching messages for {title}..."):
                    try:
                        msgs = list(client_chat.list_messages(parent=conv.name))
                        for m in msgs:
                            role = (
                                "user"
                                if getattr(m, "user_message", None)
                                else "assistant"
                            )
                            with st.chat_message(role):
                                if role == "user":
                                    st.markdown(m.user_message.text)
                                else:
                                    content = _convert_history_message_to_dict(m)
                                    render_assistant_message(content)
                    except Exception as e:
                        st.error(f"Message load error: {e}")


conversations_main()
