# === FILE: error_handling.py (unchanged behavior; project from env/ADC) ===
import functools
import logging
import sys
import traceback
import os

import streamlit as st
from google.cloud import logging as cloud_logging
from google.api_core.exceptions import GoogleAPICallError, ServiceUnavailable

# --- GCP Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

# Prefer explicit env project, else ADC will infer
logging_project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
client = cloud_logging.Client(project=logging_project_id) if logging_project_id else cloud_logging.Client()
logger = client.logger("ca-api-v2")

def handle_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ServiceUnavailable as e:
            st.warning("⚠️  The Google service is temporarily unavailable. Please try again in a few seconds.")
            log_error(f"503 ServiceUnavailable: {e}", st.session_state.get("user_email"))
            st.stop()
        except GoogleAPICallError as e:
            st.error(f"😞  A Google API error occurred: {e.message} {traceback.format_exc()}")
            log_error(f"GCP API error: {e} | {traceback.format_exc()}", st.session_state.get("user_email"))
            st.stop()
        except Exception as e:
            st.exception(f"An unexpected application error occurred in '{func.__name__}': {e}")
            log_error(f"{e} | {traceback.format_exc()}", st.session_state.get("user_email"))
            st.stop()
    return wrapper

def handle_streamlit_exception(e: Exception, context_name: str = ""):
    st.exception(e)
    log_error(f"{e} | {traceback.format_exc()}", st.session_state.get("user_email", None))
    st.stop()

def log_user_login(user_email):
    logger.log_struct({"message": f"User logged in: {user_email}", "authenticated_user": f"{user_email}"}, severity="INFO")

def log_user_logout(user_email):
    logger.log_struct({"message": f"User logged out: {user_email}", "authenticated_user": f"{user_email}"}, severity="INFO")

def log_error(error_info, user_id):
    payload = {"message": f"Error info: {error_info}", "user_id": user_id}
    logger.log_struct(payload, severity="ERROR")
