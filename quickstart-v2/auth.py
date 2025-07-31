# === FILE: auth.py ===
import os
import urllib.parse
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from google.api_core.exceptions import GoogleAPICallError
from google.auth.transport import requests as google_auth_requests
from google.cloud import firestore
from google.oauth2 import id_token as google_id_token
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app_secrets import get_secret
from error_handling import (
    handle_errors,
    handle_streamlit_exception,
    log_error,
    log_user_login,
    log_user_logout,
)

load_dotenv()

GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
if not GCP_PROJECT:
    st.exception("GCP_PROJECT or GOOGLE_CLOUD_PROJECT is required.")
    st.stop()

CLIENT_ID = get_secret(GCP_PROJECT, "secret-ca-api-clientid")
CLIENT_SECRET = get_secret(GCP_PROJECT, "secret-ca-api-clientsecret")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8501")

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

FIRESTORE_TOKEN_COLLECTION = "user_oauth_tokens"

class Authenticator:
    """
    Handles OAuth login, token persistence in Firestore, and
    reconstruction of Credentials with expiry.
    """

    def __init__(self, cookies):
        self.cookies = cookies
        self.db = self._get_firestore_client()
        self._init_session_state()

    @staticmethod
    @st.cache_resource(show_spinner=False)
    @handle_errors
    def _get_firestore_client():
        return firestore.Client(project=GCP_PROJECT)

    @staticmethod
    @handle_errors
    def _init_session_state():
        for k in ["auth_token_info", "user_email", "creds"]:
            if k not in st.session_state:
                st.session_state[k] = None

    @handle_errors
    def _save_token_to_firestore(self, user_email, token_data):
        token_with_ts = token_data.copy()
        token_with_ts["last_updated"] = firestore.SERVER_TIMESTAMP
        self.db.collection(FIRESTORE_TOKEN_COLLECTION).document(user_email).set(
            token_with_ts
        )

    @handle_errors
    def _load_token_from_firestore(self, user_email):
        doc = self.db.collection(FIRESTORE_TOKEN_COLLECTION).document(user_email).get()
        return doc.to_dict() if doc.exists else None

    @staticmethod
    @handle_errors
    def _create_credentials_object(token_data):
        # Safely parse expiry if present
        expiry = None
        if "expiry" in token_data:
            try:
                expiry = datetime.fromisoformat(token_data["expiry"])
            except Exception:
                expiry = None
        creds = Credentials(
            token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scopes=SCOPES,
        )
        if expiry:
            creds.expiry = expiry
        return creds


    @handle_errors
    def _clear_token_from_firestore(self, user_email):
        """Remove the stored OAuth token for this user."""
        self.db.collection(FIRESTORE_TOKEN_COLLECTION).document(user_email).delete()

    @handle_errors
    def check_session(self):
        if st.session_state.get("user_email"):
            return

        user_email = self.cookies.get("user_email")
        if not user_email:
            return

        token = self._load_token_from_firestore(user_email)
        if not token:
            self.cookies["user_email"] = ""
            return

        creds = self._create_credentials_object(token)
        st.session_state["auth_token_info"] = token
        st.session_state["user_email"] = user_email
        st.session_state["creds"] = creds

    @handle_errors
    def _build_flow(self, state=None):
        return Flow.from_client_config(
            {
                "web": {
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [REDIRECT_URI],
                }
            },
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
            state=state,
        )

    @handle_errors
    def login_widget(self):
        code = st.query_params.get("code")
        error = st.query_params.get("error")

        if st.session_state.get("user_email"):
            return

        if error:
            st.exception(f"OAuth error: {error}")
            st.query_params.clear()
            return

        if code:
            flow = self._build_flow()
            flow.fetch_token(code=code)
            creds = flow.credentials

            try:
                idinfo = google_id_token.verify_oauth2_token(
                    creds.id_token, google_auth_requests.Request(), CLIENT_ID
                )
            except Exception as ex:
                st.exception("Failed to verify ID token.")
                log_error(f"ID token verification failed: {ex}", None)
                return

            user_email = idinfo.get("email")
            token_data = {
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "id_token": creds.id_token,
                "scope": " ".join(creds.scopes),
                "email": user_email,
                "id_token_claims": idinfo,
                "expiry": creds.expiry.isoformat(),
            }

            self._save_token_to_firestore(user_email, token_data)
            self.cookies["user_email"] = user_email

            st.session_state["auth_token_info"] = token_data
            st.session_state["user_email"] = user_email
            st.session_state["creds"] = self._create_credentials_object(token_data)
            st.session_state["user_info"] = {
                "email": user_email,
                "name": idinfo.get("name", user_email),
                "picture": idinfo.get("picture"),
            }

            st.query_params.clear()
            st.rerun()
            return

        st.info("Please log in to continue.")
        flow = self._build_flow()
        auth_url, _ = flow.authorization_url(
            prompt="consent", access_type="offline", include_granted_scopes="false"
        )
        st.markdown(
            f'<a href="{auth_url}" target="_self"><button>Login with Google</button></a>',
            unsafe_allow_html=True,
        )

    @handle_errors
    def logout_widget(self):
        if st.button("Logout"):
            user_email = st.session_state.get("user_email")
            if user_email:
                self.db.collection(FIRESTORE_TOKEN_COLLECTION).document(
                    user_email
                ).delete()
                self.cookies["user_email"] = ""
            for k in ["user_email", "auth_token_info", "creds"]:
                st.session_state.pop(k, None)
            st.rerun()
