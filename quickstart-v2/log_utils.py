import functools
import logging
import sys
import traceback

import streamlit as st
from google.cloud import logging as cloud_logging

logging_project_id = "g-sql-morphic-luminous"
client = cloud_logging.Client(project=logging_project_id)
logger = client.logger("ca-api-v2")


def handle_errors(func):
    """Decorator to catch exceptions, log them, and halt Streamlit immediately."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = str(e)
            if (
                "503" in error_msg
                or "service is currently unavailable" in error_msg.lower()
            ):
                st.warning(
                    "⚠️ The service is temporarily unavailable (503 error). Please try again later."
                )
            else:
                st.exception(
                    f"An unexpected application error occurred in '{func.__name__}' {str(e)}."
                )

            log_error(
                f"{e} | {traceback.format_exc()}", st.session_state.get("user_id", None)
            )
            st.stop()

    return wrapper


def handle_streamlit_exception(e: Exception, context_name: str = ""):
    """
    Logs exceptions to GCP and displays user-friendly messages in Streamlit.
    """
    message = f"An unexpected error occurred in '{context_name}'."
    st.exception(e)
    log_error(f"{e} | {traceback.format_exc()}", st.session_state.get("user_id", None))
    st.stop()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)


def log_error(error_info, user_id):
    """Logs an error message with a user ID."""
    payload = {"message": f"Error info: {error_info}", "user_id": user_id}
    logger.log_struct(payload, severity="ERROR")


def log_user_login(user_email):
    """Logs a successful user login."""
    logger.log_struct(
        {
            "message": f"User logged in: {user_email}",
            "authenticated_user": f"{user_email}",
        },
        severity="Info",
    )
    st.toast(f"user {user_email} authenticated")
