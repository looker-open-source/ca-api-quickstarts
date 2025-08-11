# === FILE: app.py ===

import os

import streamlit as st
from dotenv import load_dotenv
from google.auth.transport.requests import Request as GoogleAuthRequest
from streamlit_cookies_manager import EncryptedCookieManager
from app_secrets import get_secret
from auth import Authenticator
from error_handling import handle_errors, handle_streamlit_exception

@handle_errors
def main_part_one():
    # --- PAGE CONFIG ---
    st.set_page_config(
        page_title="Conversational Analytics API",
        page_icon="🗣️",
        layout="wide",
        initial_sidebar_state="expanded",
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

    if (
        "auth_token_info" not in st.session_state
        or st.session_state["auth_token_info"] is None
    ):
        st.error("Login succeeded but token info is missing. Please log in again.")
        auth.logout_widget() # Give user a way to escape
        st.stop()

    # --- TOKEN REFRESH LOGIC ---
    creds = st.session_state.get("creds")
    if creds and creds.refresh_token:
        try:
            if not creds.valid:
                # The credentials object is stale, refresh it
                creds.refresh(GoogleAuthRequest())
                
                # Create a complete, updated token dictionary for saving
                updated_token_info = st.session_state["auth_token_info"].copy()
                updated_token_info["access_token"] = creds.token
                if creds.expiry:
                    updated_token_info["expiry"] = creds.expiry.isoformat()
                # Ensure the refresh token is explicitly preserved
                updated_token_info["refresh_token"] = creds.refresh_token 

                # Update session state with the new, authoritative data
                st.session_state["creds"] = creds
                st.session_state["auth_token_info"] = updated_token_info
                
                # Save the complete token data back to Firestore
                auth._save_token_to_firestore(
                    st.session_state["user_email"],
                    updated_token_info,
                )

        except Exception as e:
            st.warning("Your session has expired or could not be refreshed. Please log in again.")
            # Clear out the invalid session state completely
            user_email_to_clear = st.session_state.get("user_email")
            if user_email_to_clear:
                auth._clear_token_from_firestore(user_email_to_clear)
            if "user_email" in cookies:
                del cookies["user_email"]
            for k in ["user_email", "auth_token_info", "creds", "user_info"]:
                st.session_state.pop(k, None)
            st.rerun()

    # --- REMAINDER OF YOUR APP LOGIC ---
    user_info = {
        "email": st.session_state.get("auth_token_info", {}).get("email"),
        "name": st.session_state.get("auth_token_info", {})
        .get("id_token_claims", {})
        .get("name"),
        "picture": st.session_state.get("auth_token_info", {})
        .get("id_token_claims", {})
        .get("picture"),
    }
    col1, col2 = st.columns([5, 1])
    with col1:
        st.title("Welcome to the Conversational Analytics API")
        st.markdown(
            """
    This application provides:

    - **Chat with your BigQuery data** - **Manage Data Agents** - **Browse Conversation History** Select a page from the sidebar to get started.
            """
        )
    with col2:
        if user_info.get("name"): # Only show popover if user info is loaded
            with st.popover(f"👤 {user_info.get('name')}", use_container_width=True, help="Click here to logout."):
                if user_info.get("picture"):
                    st.image(user_info["picture"], width=80)
                st.markdown(f"**{user_info.get('name')}**")
                st.caption(user_info.get("email"))
                st.divider()
                if st.button("Logout", use_container_width=True):
                    auth._clear_token_from_firestore(st.session_state["user_email"])
                    if "user_email" in cookies:
                         del cookies["user_email"]
                    for k in ["user_email", "auth_token_info", "creds", "user_info"]:
                        st.session_state.pop(k, None)
                    st.rerun()

    # --- SIDEBAR NAVIGATION NOTICE ---
    st.sidebar.title("Navigation")
    st.sidebar.info("Choose one: Chat with your data, Agents, Conversations")


if __name__ == "__main__":
    main_part_one()