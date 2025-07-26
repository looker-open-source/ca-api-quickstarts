# auth.py
import os
import streamlit as st
import urllib.parse

from dotenv import load_dotenv
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import firestore
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token
from app_secrets import get_secret
from error_handling import (
    handle_errors,
    handle_streamlit_exception,
    log_error,
    log_user_login,
    log_user_logout,
)

load_dotenv()

GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLIENT_ID     = get_secret(GCP_PROJECT, "ca-api-quickstart-v2-GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = get_secret(GCP_PROJECT, "ca-api-quickstart-v2-GOOGLE_CLIENT_SECRET")

# Alias to the names used by Flow.from_client_config
CLIENT_ID     = GOOGLE_CLIENT_ID
CLIENT_SECRET = GOOGLE_CLIENT_SECRET

# Other settings
# NEW: Changed collection name to reflect it's session-based
FIRESTORE_TOKEN_COLLECTION = "session_oauth_tokens"
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8501")
SCOPES = sorted([
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/datastore",
])


class Authenticator:
    """
    Handles OAuth via Firestore-backed tokens and session persistence.
    """
    def __init__(self, cookies):
        self.cookies = cookies
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
        for key in ["auth_token_info", "user_email", "creds"]:
            st.session_state.setdefault(key, None)

    @handle_errors
    def logout(self):
        # MODIFIED: Use the session_id stored in the 'cookie' to find the right document
        session_id_to_clear = st.session_state.get("session_id")
        if session_id_to_clear:
            self._clear_token_from_firestore(session_id_to_clear)

        user_email = st.session_state.get("user_email")
        if user_email:
            log_user_logout(user_email)

        for key in ["user_email", "auth_token_info", "creds", "user_info", "session_id"]:
            st.session_state.pop(key, None)
        
        # Clear query params to ensure a clean slate
        st.query_params.clear()
        st.rerun()

    # — Firestore token management —
    # MODIFIED: These functions now use a generic 'doc_id' which will be the session_id
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

    # — OAuth2 Flow builder —
    @handle_errors
    def _build_flow(self, state=None):
        return Flow.from_client_config(
            {
                "web": {
                    "client_id":     CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                    "token_uri":     "https://oauth2.googleapis.com/token",
                    "redirect_uris": [REDIRECT_URI],
                }
            },
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
            state=state,
        )

    @staticmethod
    @handle_errors
    def _create_credentials_object(token_data):
        return Credentials(
            token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scopes=SCOPES,
        )

    # --- MAJOR CHANGE ---
    # MODIFIED: The session check is now based on the session_id from the URL
    @handle_errors
    def check_session(self):
        # If already logged in within this run, nothing to do
        if st.session_state.get("user_email"):
            return

        # Get the persistent session_id from the session state (populated from URL in app.py)
        session_id = st.session_state.get("session_id")
        if not session_id:
            return  # No session_id means a fresh visit, so they need to log in.

        # Try to load the token using the session_id as the document key
        token = self._load_token_from_firestore(session_id)
        if not token:
            return # No token found for this session ID.

        # Token found! Populate the session state.
        user_email = token.get("email")
        st.session_state["auth_token_info"] = token
        st.session_state["user_email"]      = user_email
        st.session_state["creds"]           = self._create_credentials_object(token)
        idinfo = token.get("id_token_claims", {})
        st.session_state["user_info"] = {
            "email":   user_email,
            "name":    idinfo.get("name"),
            "picture": idinfo.get("picture"),
        }


    @handle_errors
    def login_widget(self):
        code  = st.query_params.get("code")
        error = st.query_params.get("error")
        if st.session_state.get("user_email"):
            return  # already in

        if error:
            st.exception(f"OAuth error: {error}")
            st.query_params.clear()
            return

        if code:
            try:
                # MODIFIED: Use session_id as state to ensure security
                flow = self._build_flow(state=st.session_state.get("session_id"))
                flow.fetch_token(code=code[0] if isinstance(code, list) else code)
                creds  = flow.credentials
                idinfo = google_id_token.verify_oauth2_token(
                    creds.id_token, google_auth_requests.Request(), CLIENT_ID
                )
                
                # MODIFIED: Use session_id from state as the document key in Firestore
                session_id = st.session_state.get("session_id")
                if not session_id:
                    st.error("Fatal: Session ID missing during OAuth callback.")
                    st.stop()

                user_email = idinfo.get("email")
                token_data = {
                    "access_token":  creds.token,
                    "refresh_token": creds.refresh_token,
                    "id_token":      creds.id_token,
                    "scope":         " ".join(creds.scopes),
                    "email":         user_email,
                    "id_token_claims": idinfo,
                }
                
                # Save token using the session_id
                self._save_token_to_firestore(session_id, token_data)

                # Populate session state for the current run
                st.session_state["auth_token_info"] = token_data
                st.session_state["user_email"]      = user_email
                st.session_state["creds"]           = self._create_credentials_object(token_data)
                st.session_state["user_info"]       = {
                    "email":   user_email,
                    "name":    idinfo.get("name"),
                    "picture": idinfo.get("picture"),
                }

                # Clear OAuth params from URL, but keep our session_id
                st.query_params.clear()
                st.query_params["session_id"] = session_id
                st.rerun()

            except Exception as ex:
                st.exception(f"OAuth error: {ex}")
                st.query_params.clear()
                return

        # Not logged in, show button
        st.info("Please log in to continue.")
        # MODIFIED: Pass session_id in the state parameter for security
        flow = self._build_flow(state=st.session_state.get("session_id"))
        auth_url, _ = flow.authorization_url(
            prompt="consent", access_type="offline", include_granted_scopes="true"
        )
        st.markdown(
            f'<a href="{auth_url}" target="_self"><button style="padding:8px 16px; background:#4CAF50; color:#fff; border:none; border-radius:4px;">Login with Google</button></a>',
            unsafe_allow_html=True
        )

    # No changes needed below this line
    @handle_errors
    def logout_widget(self):
        if st.button("Logout"):
            self.logout()

    @handle_errors
    def get_user_name(self):
        token_info = st.session_state.get("auth_token_info") or {}
        claims     = token_info.get("id_token_claims", {})
        return claims.get("name") or st.session_state.get("user_email")