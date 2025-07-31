# setup.py
import streamlit as st
import os
import pandas as pd
import altair as alt
import proto
import google.auth

from streamlit_cookies_manager import EncryptedCookieManager
from datetime import datetime
from dotenv import load_dotenv
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import geminidataanalytics
from google.protobuf import field_mask_pb2
from google.protobuf.json_format import MessageToDict
import google.api_core.exceptions

from app_secrets import get_secret
from auth import Authenticator
from error_handling import handle_streamlit_exception, log_error

os.environ["GRPC_POLL_STRATEGY"] = "poll"

load_dotenv()

# --- CONSTANTS ---
WIDGET_BILLING_PROJECT = "billing_project"
WIDGET_BQ_PROJECT_ID = "bq_project_id"
WIDGET_BQ_DATASET_ID = "bq_dataset_id"
WIDGET_BQ_TABLE_ID = "bq_table_id"
WIDGET_SYSTEM_INSTRUCTION = "system_instruction"
SESSION_MESSAGES = "messages"
SESSION_CONVERSATION_ID = "conversation_id"
SESSION_DATA_AGENT_ID = "data_agent_id"
SESSION_PREV_BQ_PROJECT_ID = "prev_bq_project_id"
SESSION_PREV_BQ_DATASET_ID = "prev_bq_dataset_id"
SESSION_PREV_BQ_TABLE_ID = "prev_bq_table_id"
SESSION_AGENTS_MAP = "all_agents_map"
SESSION_CONVERSATIONS = "all_conversations"
USER_INFO_EMAIL = "email"
USER_INFO_NAME = "name"
USER_INFO_PICTURE = "picture"
CHAT_ROLE_USER = "user"
CHAT_ROLE_ASSISTANT = "assistant"
RESULT_SQL = "sql"
RESULT_DATAFRAME = "dataframe"
RESULT_SUMMARY = "summary"
RESULT_HAS_CHART = "has_chart"
GENERAL_SYSTEM_INSTRUCTIONS = """When a user asks for both the highest/maximum and lowest/minimum of a value, you MUST return both the top and bottom records. Use a UNION ALL statement to combine the two queries. Also, only render a chart or visualization if the user specifically asks for one."""


# --- HELPER FUNCTIONS (SHARED) ---
@st.cache_data
def get_default_project_id():
    try:
        _, project_id = google.auth.default()
        return project_id
    except google.auth.exceptions.DefaultCredentialsError:
        return None
    except Exception as e:
        handle_streamlit_exception(e, "get_default_project_id")

def _convert_proto_to_dict(msg):
    if isinstance(msg, proto.marshal.collections.maps.MapComposite):
        return {k: _convert_proto_to_dict(v) for k, v in msg.items()}
    if isinstance(msg, proto.marshal.collections.RepeatedComposite):
        return [_convert_proto_to_dict(x) for x in msg]
    if isinstance(msg, (int, float, str, bool)):
        return msg
    return MessageToDict(msg, preserving_proto_field_name=True)

def render_assistant_message(content):
    if content.get("summary"):
        st.markdown(content["summary"])
    if content.get("sql"):
        with st.expander("Show Generated SQL"):
            st.code(content["sql"], language="sql")
    df = content.get("dataframe")
    if df is not None and not df.empty:
        st.subheader("Data Result")
        st.dataframe(df)
        if len(df) > 1 and content.get("has_chart"):
            st.subheader("Generated Chart")
            try:
                x, y = df.columns[0], df.columns[1]
                chart = (
                    alt.Chart(df)
                    .mark_bar()
                    .encode(
                        x=alt.X(f"{x}:N", sort="-y", title=x.title()),
                        y=alt.Y(f"{y}:Q", title=y.title()),
                        tooltip=list(df.columns),
                    )
                    .properties(title=f"{y.title()} by {x.title()}")
                )
                st.altair_chart(chart, use_container_width=True)
            except Exception as e:
                st.error(f"Could not generate chart: {e}")

def _convert_history_message_to_dict(msg):
    m = msg.system_message
    gen_sql, summary = "", ""
    df = pd.DataFrame()
    has_chart = False
    if getattr(m, "text", None) and m.text.parts:
        summary += "".join(m.text.parts)
    if getattr(m, "data", None):
        if m.data.generated_sql:
            gen_sql = m.data.generated_sql
        rows = getattr(m.data.result, "data", [])
        if rows:
            df = pd.DataFrame(
                [_convert_proto_to_dict(r) for r in rows],
                columns=[f.name for f in m.data.result.schema.fields],
            )
    if getattr(m, "chart", None):
        has_chart = True
    return {"sql": gen_sql, "dataframe": df, "summary": summary, "has_chart": has_chart}


# --- MAIN INITIALIZATION FUNCTION ---
def initialize_app():
    """
    Performs all the common setup for every page:
    - Sets page config and styles
    - Handles authentication and credential refreshing
    - Renders the header and common sidebar elements
    - Initializes and returns API clients and user inputs
    """
    # --- PAGE CONFIG ---
    st.set_page_config(
        page_title="Conversational Analytics API",
        page_icon="🗣️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    # --- STYLES ---
    hide_streamlit_style = """
    <style>
    .css-hi6a2p {padding-top: 0rem;}
    :root {
        --sidebar-width: 18rem;
        --page-padding: 1rem;
        --chat-input-border-color: #28a745;
    }
    div.block-container {
        padding-top: 1rem;
    }
    [data-testid="stChatInputContainer"], [data-testid="stChatInput"] {
        position: fixed !important;
        bottom: 0 !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        width: 50vw !important;
        max-width: calc(100vw - var(--sidebar-width) - var(--page-padding)*2) !important;
        background: #fff !important;
        padding: 0.75rem 1rem !important;
        box-shadow: 0 -2px 8px rgba(0,0,0,0.1) !important;
        z-index: 9999 !important;
        border-radius: 8px !important;
    }
    [data-testid="stVerticalBlock"] {
        padding-bottom: 6rem !important;
    }
    .suggested-questions [data-testid="stButton"] {
        border: 2px solid var(--chat-input-border-color) !important;
        border-radius: 8px !important;
    }
    div[data-testid="stPopover"] > button {
        border: none;
        background: #f0f2f6;
        color: #31333F;
        font-weight: bold;
        border-radius: 8px;
        padding: 0.5rem 1rem;
    }
    div[data-testid="stPopover"] > button:hover {
        background: #e0e2e6;
    }
    </style>
    """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

    # --- AUTHENTICATION ---
    cookies = EncryptedCookieManager(
        password=get_secret(
            os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT"),
            "EncryptedCookieManager-secret",
        )
    )
    if not cookies.ready():
        st.info("Caching data, one sec...")
        st.stop()

    auth = Authenticator(cookies)
    auth.check_session()

    if not st.session_state.get("user_email"):
        auth.login_widget()
        st.stop()

    if "auth_token_info" not in st.session_state or st.session_state["auth_token_info"] is None:
        st.error("Login succeeded but token info missing; please re-authenticate.")
        st.stop()

    credentials = st.session_state.get("creds")
    if credentials and credentials.refresh_token:
        try:
            credentials.refresh(GoogleAuthRequest())
            st.session_state["auth_token_info"]["access_token"] = credentials.token
            st.session_state["auth_token_info"]["expiry"] = credentials.expiry.isoformat()
            auth._save_token_to_firestore(st.session_state["user_email"], st.session_state["auth_token_info"])
        except Exception as e:
            st.error(f"Could not refresh credentials: {e}")
            st.stop()

    # --- CLIENT INITIALIZATION ---
    data_agent_client = geminidataanalytics.DataAgentServiceClient(credentials=credentials)
    data_chat_client = geminidataanalytics.DataChatServiceClient(credentials=credentials)

    # --- HEADER AND USER INFO ---
    user_info = {
        "email": st.session_state["auth_token_info"].get("email"),
        "name": st.session_state["auth_token_info"]["id_token_claims"].get("name"),
        "picture": st.session_state["auth_token_info"]["id_token_claims"].get("picture"),
    }
    header_col1, header_col2 = st.columns([5, 1])
    with header_col1:
        st.title("Conversational Analytics API")
    with header_col2:
        with st.popover(f"👤 {user_info.get(USER_INFO_NAME)}", use_container_width=True):
            if user_info.get(USER_INFO_PICTURE):
                st.image(user_info[USER_INFO_PICTURE], width=100)
            st.markdown(f"**{user_info.get(USER_INFO_NAME)}**")
            st.caption(f"{user_info.get(USER_INFO_EMAIL)}")
            st.divider()
            if st.button("Logout", use_container_width=True):
                user_email = st.session_state.get("user_email")
                if user_email:
                    auth._clear_token_from_firestore(user_email)
                    cookies["user_email"] = ""
                for key in ["user_email", "auth_token_info", "creds"]:
                    st.session_state.pop(key, None)
                st.rerun()

    # --- COMMON SIDEBAR ELEMENTS ---
    st.sidebar.header("Settings")
    billing_project = st.sidebar.text_input(
        "GCP Billing Project ID", get_default_project_id(), key=WIDGET_BILLING_PROJECT
    )
    with st.sidebar.expander("BigQuery Data Source", expanded=True):
        st.caption("You can use the default public datasets or enter your own.")
        bq_project_id = st.text_input("BQ Project ID", value="bigquery-public-data", key=WIDGET_BQ_PROJECT_ID)
        bq_dataset_id = st.text_input("BQ Dataset ID", value="faa", key=WIDGET_BQ_DATASET_ID)
        bq_table_id = st.text_input("BQ Table ID", value="us_airports", key=WIDGET_BQ_TABLE_ID)

        prev_proj, prev_ds, prev_tbl = (st.session_state.get(k) for k in [SESSION_PREV_BQ_PROJECT_ID, SESSION_PREV_BQ_DATASET_ID, SESSION_PREV_BQ_TABLE_ID])
        if (prev_proj, prev_ds, prev_tbl) != (bq_project_id, bq_dataset_id, bq_table_id):
            st.session_state[SESSION_PREV_BQ_PROJECT_ID] = bq_project_id
            st.session_state[SESSION_PREV_BQ_DATASET_ID] = bq_dataset_id
            st.session_state[SESSION_PREV_BQ_TABLE_ID] = bq_table_id
            st.session_state[SESSION_DATA_AGENT_ID] = None
            st.session_state[SESSION_CONVERSATION_ID] = None
            st.session_state[SESSION_MESSAGES] = []
            st.rerun()

    with st.sidebar.expander("System Instructions", expanded=True):
        user_system_instruction = st.text_area("Agent Instructions", value="", key=WIDGET_SYSTEM_INSTRUCTION, height=200)

    if st.sidebar.button("Clear Chat 🧹"):
        st.session_state[SESSION_MESSAGES] = []
        st.rerun()

    # Return clients and user inputs for the page to use
    return {
        "data_agent_client": data_agent_client,
        "data_chat_client": data_chat_client,
        "billing_project": billing_project,
        "bq_project_id": bq_project_id,
        "bq_dataset_id": bq_dataset_id,
        "bq_table_id": bq_table_id,
        "user_system_instruction": user_system_instruction,
    }