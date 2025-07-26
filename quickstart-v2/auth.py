# --- START FILE: auth.py ---
import os
import uuid
from datetime import datetime, timedelta

import streamlit as st
from dotenv import load_dotenv
from google.api_core.exceptions import GoogleAPICallError
from google.auth.transport import requests as google_auth_requests
from google.cloud import firestore
from google.oauth2 import id_token as google_id_token
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app_secrets import get_secret
from error_handling import (handle_errors, log_user_login, log_user_logout)

load_dotenv()

# --- Constants ---
GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
CLIENT_ID = get_secret(GCP_PROJECT, "ca-api-quickstart-v2-GOOGLE_CLIENT_ID")
CLIENT_SECRET = get_secret(GCP_PROJECT, "ca-api-quickstart-v2-GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8501")
FIRESTORE_TOKEN_COLLECTION = "session_oauth_tokens"
SCOPES = sorted([
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/drive",
])

class Authenticator:
    """
    Handles OAuth via Firestore-backed tokens and persistent browser cookies.
    """

    def __init__(self, cookie_manager):
        self.cookies = cookie_manager
        self.db = self._get_firestore_client()
        self._init_session_state()

    @st.cache_resource(show_spinner=False)
    @handle_errors
    def _get_firestore_client(_self):
        try:
            return firestore.Client(project=GCP_PROJECT)
        except Exception as e:
            st.exception(f"🔥 Could not connect to Firestore. Error: {e}")
            st.stop()

    @staticmethod
    @handle_errors
    def _init_session_state():
        for key in ["auth_token_info", "user_email", "creds", "user_info"]:
            st.session_state.setdefault(key, None)

    @handle_errors
    def logout(self):
        """
        Clears the session by deleting the Firestore token, browser cookie,
        and Streamlit session state.
        """
        session_cookie = self.cookies.get('user_session_cookie')
        if session_cookie:
            self._clear_token_from_firestore(session_cookie)
            self.cookies.delete('user_session_cookie')

        user_email = st.session_state.get("user_email")
        if user_email:
            log_user_logout(user_email)

        # Thoroughly clear the session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]

        st.rerun()

    @handle_errors
    def check_session(self):
        """
        Checks for a valid persistent session cookie and loads the user's
        session from Firestore if one is found.
        """
        if st.session_state.get("user_email"):
            return  # Already logged in for this script run

        session_cookie = self.cookies.get('user_session_cookie')
        if not session_cookie:
            return  # No cookie, user must log in

        token = self._load_token_from_firestore(session_cookie)
        if not token:
            self.cookies.delete('user_session_cookie') # Clean up invalid cookie
            return

        # Token found, populate the session
        user_email = token.get("email")
        st.session_state["auth_token_info"] = token
        st.session_state["user_email"] = user_email
        st.session_state["creds"] = self._create_credentials_object(token)
        idinfo = token.get("id_token_claims", {})
        st.session_state["user_info"] = {
            "email": user_email,
            "name": idinfo.get("name"),
            "picture": idinfo.get("picture"),
        }

    @handle_errors
    def login_widget(self):
        """
        Displays the login button or handles the OAuth callback to
        create and persist a new user session.
        """
        code = st.query_params.get("code")
        if st.session_state.get("user_email"):
            return # Already logged in

        if code:
            try:
                flow = self._build_flow()
                flow.fetch_token(code=code[0] if isinstance(code, list) else code)
                creds = flow.credentials
                idinfo = google_id_token.verify_oauth2_token(
                    creds.id_token, google_auth_requests.Request(), CLIENT_ID
                )

                user_email = idinfo.get("email")
                token_data = {
                    "access_token": creds.token, "refresh_token": creds.refresh_token,
                    "id_token": creds.id_token, "scope": " ".join(creds.scopes),
                    "email": user_email, "id_token_claims": idinfo,
                }

                # --- FIX START: Populate session state immediately ---
                st.session_state["auth_token_info"] = token_data
                st.session_state["user_email"] = user_email
                st.session_state["creds"] = self._create_credentials_object(token_data)
                st.session_state["user_info"] = {
                    "email": user_email,
                    "name": idinfo.get("name"),
                    "picture": idinfo.get("picture"),
                }
                log_user_login(user_email)
                # --- FIX END ---

                # Create and persist the session for future visits
                session_cookie_value = str(uuid.uuid4())
                self._save_token_to_firestore(session_cookie_value, token_data)
                self.cookies.set(
                    'user_session_cookie',
                    session_cookie_value,
                    expires_at=datetime.now() + timedelta(days=30)
                )

                # Clear OAuth query params and rerun to start the app cleanly
                st.query_params.clear()
                st.rerun()
            except Exception as ex:
                st.exception(f"OAuth error: {ex}")
                st.query_params.clear()
                return

        # Show login button if not logged in and no auth code in URL
        flow = self._build_flow()
        auth_url, _ = flow.authorization_url(
            prompt="consent", access_type="offline", include_granted_scopes="true"
        )
        st.markdown(
            f'<a href="{auth_url}" target="_self" style="text-decoration: none;"><button style="padding: 10px 24px; font-size: 16px; background-color: #4285F4; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">Login with Google</button></a>',
            unsafe_allow_html=True
        )


    # --- Internal Helper Methods ---

    @handle_errors
    def _save_token_to_firestore(self, doc_id, token):
        try:
            token_with_ts = {**token, "last_updated": firestore.SERVER_TIMESTAMP}
            self.db.collection(FIRESTORE_TOKEN_COLLECTION).document(doc_id).set(token_with_ts)
        except GoogleAPICallError as e:
            st.exception(f"🔥 Firestore save error: {e}")

    @handle_errors
    def _load_token_from_firestore(self, doc_id):
        try:
            doc = self.db.collection(FIRESTORE_TOKEN_COLLECTION).document(doc_id).get()
            return doc.to_dict() if doc.exists else None
        except GoogleAPICallError as e:
            st.exception(f"🔥 Firestore load error: {e}")
            return None

    @handle_errors
    def _clear_token_from_firestore(self, doc_id):
        try:
            self.db.collection(FIRESTORE_TOKEN_COLLECTION).document(doc_id).delete()
        except GoogleAPICallError as e:
            st.exception(f"🔥 Firestore clear error: {e}")

    @handle_errors
    def _build_flow(self, state=None):
        return Flow.from_client_config(
            {"web": {
                "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }},
            scopes=SCOPES, redirect_uri=REDIRECT_URI, state=state,
        )

    @staticmethod
    @handle_errors
    def _create_credentials_object(token_data):
        return Credentials(
            token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
            scopes=SCOPES,
        )
# --- END FILE: auth.py ---