import os
import streamlit as st
from dotenv import load_dotenv
from streamlit_cookies_manager import EncryptedCookieManager
from google.auth.transport.requests import Request as GoogleAuthRequest
from app_secrets import get_secret
from auth import Authenticator
from error_handling import handle_errors

@handle_errors
def main_part_one():
    # --- PAGE CONFIG ---
    st.set_page_config(
        page_title="Conversational Analytics API",
        page_icon="🗣️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown("""
        <style>
        .block-container {
            padding-top: 0rem;
        }
        </style>
        """, unsafe_allow_html=True)

    # --- LOAD ENVIRONMENT VARIABLES ---
    load_dotenv()

    # --- AUTHENTICATION SETUP ---
    cookies = EncryptedCookieManager(
        password=get_secret(
            os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT"),
            "EncryptedCookieManager-secret",
        )
    )
    if not cookies.ready():
        st.info("Initializing session, please wait…")
        st.stop()

    auth = Authenticator(cookies)
    auth.check_session()

    if not st.session_state.get("user_email"):
        auth.login_widget()
        st.stop()

    if "auth_token_info" not in st.session_state or st.session_state["auth_token_info"] is None:
        st.error("Login succeeded but token info missing; please re-authenticate.")
        st.stop()

    # --- REFRESH TOKEN IF NEEDED ---
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

    user_info = {
        "email": st.session_state["auth_token_info"].get("email"),
        "name": st.session_state.get("auth_token_info", {}).get("id_token_claims", {}).get("name"),
        "picture": st.session_state.get("auth_token_info", {}).get("id_token_claims", {}).get("picture"),
    }
    col1, col2 = st.columns([5, 1])
    with col1:
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
        with st.popover(f"👤 {user_info.get('name')}", use_container_width=True):
            if user_info.get("picture"):
                st.image(user_info["picture"], width=80)
            st.markdown(f"**{user_info.get('name')}**")
            st.caption(user_info.get("email"))
            st.divider()
            if st.button("Logout", use_container_width=True):
                auth._clear_token_from_firestore(st.session_state["user_email"])
                cookies["user_email"] = ""
                for k in ["user_email", "auth_token_info", "creds"]:
                    st.session_state.pop(k, None)
                st.rerun()

    # --- SIDEBAR NAVIGATION NOTICE ---
    st.sidebar.title("Navigation")
    st.sidebar.info("Choose one: Chat with your data, Agents, Conversations")

main_part_one()