import os

import streamlit as st
from dotenv import load_dotenv
from google.cloud import firestore, secretmanager
from streamlit_cookies_manager import EncryptedCookieManager

load_dotenv()
import base64
import json
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from streamlit_oauth import OAuth2Component

from log_utils import handle_errors, handle_streamlit_exception

GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")


FS_USER_TOKENS_COLLECTION = "user_tokens"
# Dictionary and Token Keys
TOKEN_ID_TOKEN = "id_token"
TOKEN_REFRESH_TOKEN = "refresh_token"
USER_INFO_EMAIL = "email"
USER_INFO_NAME = "name"
USER_INFO_PICTURE = "picture"
OAUTH_RESULT_TOKEN = "token"
SESSION_USER_ID = "user_id"
# Dictionary and Token Keys
TOKEN_ID_TOKEN = "id_token"
TOKEN_REFRESH_TOKEN = "refresh_token"
USER_INFO_EMAIL = "email"
USER_INFO_NAME = "name"
USER_INFO_PICTURE = "picture"
OAUTH_RESULT_TOKEN = "token"
# Session State Keys
SESSION_LOGGED_IN = "logged_in"
SESSION_TOKEN = "token"
SESSION_CREDS = "creds"
SESSION_USER_INFO = "user_info"
SESSION_USER_ID = "user_id"

def access_secret_version(secret_id, version_id="latest"):
    """
    Accesses the payload of the specified secret version.
    Args:
        secret_id (str): The ID of the secret (e.g., "my-api-key").
        version_id (str): The version of the secret to access (e.g., "1", "2", or "latest").
                          Defaults to "latest".
    Returns:
        str: The secret payload as a string.
    """
    client = secretmanager.SecretManagerServiceClient()

    name = f"projects/{GOOGLE_CLOUD_PROJECT}/secrets/{secret_id}/versions/{version_id}"

    try:
        response = client.access_secret_version(request={"name": name})
        payload = response.payload.data.decode("UTF-8")
        return payload
    except Exception as e:
        print(f"Error accessing secret {secret_id} version {version_id}: {e}")
        return None


try:
    db = firestore.Client()
except Exception as e:
    handle_streamlit_exception(e, "db = firestore.Client()")
    st.exception(e)
    db = None
    st.stop()

cookie_manager = EncryptedCookieManager(
    password=access_secret_version("EncryptedCookieManager-secret")
)
if not cookie_manager.ready():
    st.stop()

# --- Environment Variables & Auth Endpoints ---
REDIRECT_URI = os.environ.get(
    "REDIRECT_URI", "https://ca-api-quickstart-v2-119408220431.us-central1.run.app"
)
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
AUTHORIZE_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
GOOGLE_CLIENT_ID = access_secret_version("ca-api-quickstart-v2-GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = access_secret_version(
    "ca-api-quickstart-v2-GOOGLE_CLIENT_SECRET"
)
OAUTH_SCOPES_STR = "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/bigquery https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/documents https://www.googleapis.com/auth/drive"
OAUTH_SCOPES = OAUTH_SCOPES_STR.split()


@handle_errors
def save_token_to_firestore(user_id, token):
    if db:
        db.collection(FS_USER_TOKENS_COLLECTION).document(user_id).set(token)


@handle_errors
def get_token_from_firestore(user_id):
    if db:
        doc = db.collection(FS_USER_TOKENS_COLLECTION).document(user_id).get()
        return doc.to_dict() if doc.exists else None
    return None


@handle_errors
def delete_token_from_firestore(user_id):
    if db:
        db.collection(FS_USER_TOKENS_COLLECTION).document(user_id).delete()


def get_user_id_from_token(token, full_payload=False):
    if TOKEN_ID_TOKEN in token:
        try:
            id_token = token[TOKEN_ID_TOKEN]
            payload = id_token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            decoded_payload = base64.urlsafe_b64decode(payload)
            user_info = json.loads(decoded_payload)
            return user_info if full_payload else user_info.get(USER_INFO_EMAIL)
        except Exception:
            return None
    return None


@handle_errors
def logout():
    """Clear session state and delete persistent token if user_id is known."""
    if SESSION_USER_ID in st.session_state and st.session_state[SESSION_USER_ID]:
        # Delete token from Firestore
        delete_token_from_firestore(st.session_state[SESSION_USER_ID])
        # Delete user_id from cookie and save changes
        del cookie_manager["user_id"]
        cookie_manager.save()

    # Clear all Streamlit session state
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


@st.cache_resource
def get_oauth2_component():
    return OAuth2Component(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        authorize_endpoint=AUTHORIZE_ENDPOINT,
        token_endpoint=TOKEN_ENDPOINT,
        refresh_token_endpoint=TOKEN_ENDPOINT,
        revoke_token_endpoint=REVOKE_ENDPOINT,
    )


st.session_state.setdefault("user_email", None)
st.session_state.setdefault("user_id", None)
st.session_state.setdefault("user_name", "User")


@handle_errors
def handle_authentication():
    st.session_state.setdefault(SESSION_LOGGED_IN, False)
    st.session_state.setdefault(SESSION_TOKEN, None)
    st.session_state.setdefault(SESSION_CREDS, None)
    st.session_state.setdefault(SESSION_USER_INFO, {})
    st.session_state.setdefault(SESSION_USER_ID, None)

    user_id_from_cookie = cookie_manager.get("user_id")

    if user_id_from_cookie and st.session_state[SESSION_USER_ID] is None:
        st.session_state[SESSION_USER_ID] = user_id_from_cookie
        st.session_state[SESSION_TOKEN] = get_token_from_firestore(user_id_from_cookie)
        if st.session_state[SESSION_TOKEN]:
            token_info_for_creds = {
                **st.session_state[SESSION_TOKEN],
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
            }
            try:
                creds = Credentials.from_authorized_user_info(token_info_for_creds)
                st.session_state[SESSION_CREDS] = creds

                user_info_payload = get_user_id_from_token(
                    st.session_state[SESSION_TOKEN], full_payload=True
                )
                if user_info_payload:
                    st.session_state[SESSION_USER_INFO] = {
                        USER_INFO_EMAIL: user_info_payload.get(USER_INFO_EMAIL),
                        USER_INFO_NAME: user_info_payload.get(USER_INFO_NAME),
                        USER_INFO_PICTURE: user_info_payload.get(USER_INFO_PICTURE),
                    }
                    st.session_state[SESSION_USER_ID] = user_info_payload.get(
                        USER_INFO_EMAIL
                    )

                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    new_token_data = json.loads(creds.to_json())
                    if (
                        TOKEN_ID_TOKEN not in new_token_data
                        and TOKEN_ID_TOKEN in st.session_state[SESSION_TOKEN]
                    ):
                        new_token_data[TOKEN_ID_TOKEN] = st.session_state[
                            SESSION_TOKEN
                        ][TOKEN_ID_TOKEN]

                    st.session_state[SESSION_TOKEN] = new_token_data
                    save_token_to_firestore(
                        st.session_state[SESSION_USER_ID], new_token_data
                    )

                st.session_state[SESSION_LOGGED_IN] = True
                return True

            except Exception as e:

                st.warning(f"Session restoration failed: {e}. Please log in again.")
                logout()

    if st.session_state[SESSION_LOGGED_IN] and st.session_state[SESSION_CREDS]:
        return True

    oauth2 = get_oauth2_component()

    left_co, center_co, right_co = st.columns([3, 2, 3])
    with center_co:
        result = oauth2.authorize_button(
            name="Login with Google",
            icon="https://www.google.com/favicon.ico",
            redirect_uri=REDIRECT_URI,
            scope=" ".join(OAUTH_SCOPES),
            extras_params={"access_type": "offline", "prompt": "consent"},
        )

    if result and OAUTH_RESULT_TOKEN in result:
        token = result[OAUTH_RESULT_TOKEN]
        user_id = get_user_id_from_token(token)
        if not user_id:
            st.error("Authentication failed: Could not retrieve user email from token.")
            st.stop()

        cookie_manager["user_id"] = user_id
        cookie_manager.expires = datetime.now() + timedelta(days=30)
        cookie_manager.save()

        st.session_state[SESSION_USER_ID] = user_id
        stored_token = get_token_from_firestore(user_id)
        if stored_token and TOKEN_REFRESH_TOKEN in stored_token:
            token[TOKEN_REFRESH_TOKEN] = stored_token[TOKEN_REFRESH_TOKEN]

        save_token_to_firestore(user_id, token)
        st.session_state[SESSION_TOKEN] = token
        st.rerun()

    if st.session_state[SESSION_TOKEN]:
        token_from_session = st.session_state[SESSION_TOKEN]
        token_info_for_creds = {
            **token_from_session,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
        }
        creds = Credentials.from_authorized_user_info(token_info_for_creds)

        if not st.session_state[SESSION_USER_INFO].get(USER_INFO_EMAIL):
            user_info_payload = get_user_id_from_token(
                st.session_state[SESSION_TOKEN], full_payload=True
            )
            if user_info_payload:
                st.session_state[SESSION_USER_INFO] = {
                    USER_INFO_EMAIL: user_info_payload.get(USER_INFO_EMAIL),
                    USER_INFO_NAME: user_info_payload.get(USER_INFO_NAME),
                    USER_INFO_PICTURE: user_info_payload.get(USER_INFO_PICTURE),
                }
                st.session_state[SESSION_USER_ID] = user_info_payload.get(
                    USER_INFO_EMAIL
                )

        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                new_token_data = json.loads(creds.to_json())
                if (
                    TOKEN_ID_TOKEN not in new_token_data
                    and TOKEN_ID_TOKEN in st.session_state[SESSION_TOKEN]
                ):
                    new_token_data[TOKEN_ID_TOKEN] = st.session_state[SESSION_TOKEN][
                        TOKEN_ID_TOKEN
                    ]

                st.session_state[SESSION_TOKEN] = new_token_data
                if st.session_state[SESSION_USER_ID]:
                    save_token_to_firestore(
                        st.session_state[SESSION_USER_ID], new_token_data
                    )
                st.toast("Session refreshed automatically.")
            except Exception as e:
                st.error(f"Failed to refresh token: {e}. Please log in again.")
                logout()
                return False

        st.session_state[SESSION_CREDS] = creds
        st.session_state[SESSION_LOGGED_IN] = True
        return True  # User is now logged in

    return False
