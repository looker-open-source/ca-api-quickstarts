import os
import uuid
import traceback
import altair as alt
import pandas as pd
import proto
import streamlit as st
import google.auth
from dotenv import load_dotenv
from extra_streamlit_components import CookieManager
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import geminidataanalytics
from google.protobuf import field_mask_pb2
from google.protobuf.json_format import MessageToDict
from auth import Authenticator
from app_secrets import get_secret
from error_handling import (
    log_error, log_user_login, log_user_logout,
    handle_errors, handle_streamlit_exception
)

os.environ['GRPC_POLL_STRATEGY'] = 'poll'

# --- Page Config ---
st.set_page_config(
    page_title="Conversational Analytics API",
    page_icon="🗣️",
    layout="wide",
    initial_sidebar_state="expanded",
)
load_dotenv()

@st.cache_data
def get_default_project_id():
    """Tries to discover the default GCP project ID from the environment."""
    try:
        _, project_id = google.auth.default()
        return project_id
    except google.auth.exceptions.DefaultCredentialsError:
        return None
    except Exception as e:
        handle_streamlit_exception(e, "get_default_project_id")

st.markdown(
    """
    <style>
      :root {
        --sidebar-width: 18rem;    /* adjust to your sidebar’s width */
        --page-padding: 1rem;      /* adjust to your page’s horizontal padding */
      }

      /* Pin, center, and cap width at 75% of the viewport */
      [data-testid="stChatInputContainer"],
      [data-testid="stChatInput"] {
        position: fixed !important;
        bottom: 0 !important;
        left: 50% !important;                           /* start at center */
        transform: translateX(-50%) !important;         /* shift back by half width */
        width: 50vw !important;                         /* 75% of the viewport width */
        max-width: calc(100vw - var(--sidebar-width) - var(--page-padding)*2) !important;
        background: #fff !important;
        padding: 0.75rem 1rem !important;
        box-shadow: 0 -2px 8px rgba(0,0,0,0.1) !important;
        z-index: 9999 !important;

        /* --- NEW LINES START --- */
        border: 2px solid #28a745 !important; /* A nice, visible green border */
        border-radius: 8px !important;      /* Optional: for rounded corners */
        /* --- NEW LINES END --- */
      }

      /* make sure your scrollable content doesn’t sit under the bar */
      [data-testid="stVerticalBlock"] {
        padding-bottom: 6rem !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)
# --- Constants & Widget Keys (no changes) ---
WIDGET_BILLING_PROJECT = "billing_project"
WIDGET_BQ_PROJECT_ID = "bq_project_id"
WIDGET_BQ_DATASET_ID = "bq_dataset_id"
WIDGET_BQ_TABLE_ID = "bq_table_id"
WIDGET_SYSTEM_INSTRUCTION = "system_instruction"
SESSION_CREDS = "creds"
SESSION_USER_INFO = "user_info"
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

# --- Helper: Convert Protobuf to dict (no changes) ---
def _convert_proto_to_dict(msg):
    if isinstance(msg, proto.marshal.collections.maps.MapComposite):
        return {k: _convert_proto_to_dict(v) for k, v in msg.items()}
    if isinstance(msg, proto.marshal.collections.RepeatedComposite):
        return [_convert_proto_to_dict(x) for x in msg]
    if isinstance(msg, (int, float, str, bool)):
        return msg
    return MessageToDict(msg, preserving_proto_field_name=True)

# --- Render Assistant Message (no changes) ---
def render_assistant_message(content):
    if content.get(RESULT_SUMMARY): st.markdown(content[RESULT_SUMMARY])
    if content.get(RESULT_SQL):
        with st.expander("Show Generated SQL"): st.code(content[RESULT_SQL], language="sql")
    df = content.get(RESULT_DATAFRAME)
    if df is not None and not df.empty:
        st.subheader("Data Result")
        st.dataframe(df)
        if content.get(RESULT_HAS_CHART):
            st.subheader("Generated Chart")
            try:
                x, y = df.columns[0], df.columns[1]
                chart = (
                    alt.Chart(df).mark_bar().encode(
                        x=alt.X(f"{x}:N", sort="-y", title=x.title()),
                        y=alt.Y(f"{y}:Q", title=y.title()),
                        tooltip=list(df.columns)
                    ).properties(title=f"{y.title()} by {x.title()}")
                )
                st.altair_chart(chart, use_container_width=True)
            except Exception as e:
                st.error(f"Could not generate chart: {e}")

# --- Process Chat Stream (no changes) ---
@handle_errors
def process_chat_stream(stream):
    gen_sql, summary, df, has_chart = "", "", pd.DataFrame(), False
    for resp in stream:
        m = resp.system_message
        if getattr(m, "data", None):
            if m.data.generated_sql: gen_sql = m.data.generated_sql
            rows = getattr(m.data.result, "data", [])
            if rows:
                df = pd.DataFrame(
                    [_convert_proto_to_dict(r) for r in rows],
                    columns=[f.name for f in m.data.result.schema.fields]
                )
        if getattr(m, "text", None) and m.text.parts: summary += "".join(m.text.parts)
        if getattr(m, "chart", None): has_chart = True
    return {RESULT_SQL: gen_sql, RESULT_DATAFRAME: df, RESULT_SUMMARY: summary, RESULT_HAS_CHART: has_chart}


# --- Authentication Flow ---
cookie_manager = CookieManager(key="user_session_cookie")
auth = Authenticator(cookie_manager)
auth.check_session()

# --- FIX: This is the authentication gate. ---
# If the user is not logged in, show the login widget and stop the script.
if not st.session_state.get("user_email"):
    st.info("Please log in to continue.")
    auth.login_widget()
    st.stop()

# --- FIX: The rest of the app is now un-indented and runs only after successful login. ---

# Sanity check for user info after login
if SESSION_USER_INFO not in st.session_state:
    st.error("Login succeeded but user info missing; please re-authenticate.")
    st.stop()
user_info = st.session_state[SESSION_USER_INFO]

# --- Refresh Credentials ---
credentials = st.session_state.get(SESSION_CREDS)
if credentials and credentials.expired and credentials.refresh_token:
    credentials.refresh(GoogleAuthRequest())

# --- Initialize GCP Clients ---
data_agent_client = geminidataanalytics.DataAgentServiceClient(credentials=credentials)
data_chat_client = geminidataanalytics.DataChatServiceClient(credentials=credentials)

# --- Default Session State ---
st.session_state.setdefault(SESSION_MESSAGES, [])
st.session_state.setdefault(SESSION_CONVERSATION_ID, None)
st.session_state.setdefault(SESSION_DATA_AGENT_ID, None)

# --- Sidebar and Configuration ---
if user_info.get(USER_INFO_PICTURE):
    st.sidebar.image(user_info[USER_INFO_PICTURE], width=100)
st.sidebar.write(f"**Name:** {user_info.get(USER_INFO_NAME)}")
st.sidebar.write(f"**Email:** {user_info.get(USER_INFO_EMAIL)}")
if st.sidebar.button("Logout"):
    auth.logout() # Logout function now correctly deletes the cookie
st.sidebar.divider()
st.sidebar.markdown("Enter your GCP project and BigQuery source below.")

billing_project = st.sidebar.text_input("GCP Billing Project ID", get_default_project_id(), key=WIDGET_BILLING_PROJECT)

x = "bigquery-public-data.faa.us_airports"
project, dataset, table = x.strip().split('.')

with st.sidebar.expander("BigQuery Data Source", expanded=True):
    bq_project_id = st.text_input("BQ Project ID", project, key=WIDGET_BQ_PROJECT_ID)
    bq_dataset_id = st.text_input("BQ Dataset ID", dataset, key=WIDGET_BQ_DATASET_ID)
    bq_table_id = st.text_input("BQ Table ID", table, key=WIDGET_BQ_TABLE_ID)
    if (
        st.session_state.get(SESSION_PREV_BQ_PROJECT_ID) != bq_project_id or
        st.session_state.get(SESSION_PREV_BQ_DATASET_ID) != bq_dataset_id or
        st.session_state.get(SESSION_PREV_BQ_TABLE_ID) != bq_table_id
    ):
        st.session_state.update({
            SESSION_DATA_AGENT_ID: None, SESSION_CONVERSATION_ID: None,
            SESSION_MESSAGES: [], SESSION_PREV_BQ_PROJECT_ID: bq_project_id,
            SESSION_PREV_BQ_DATASET_ID: bq_dataset_id, SESSION_PREV_BQ_TABLE_ID: bq_table_id
        })
        st.rerun()

with st.sidebar.expander("System Instructions", expanded=True):
    system_instruction = st.text_area("Agent Instructions", key=WIDGET_SYSTEM_INSTRUCTION)

st.title("Conversational Analytics API")

# --- UI Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(["Chat", "Data Agent Management", "Conversation History", "Update Data Agent"])


with tab1:
    st.header("Ask a question below...")
    if not all([billing_project, bq_project_id, bq_dataset_id, bq_table_id]):
        st.warning("👋 Please complete all GCP and BigQuery details in the sidebar to activate the chat.")
        st.stop()

    if not st.session_state.get("data_agent_id"):
        agent_id = f"agent_{pd.Timestamp.now():%Y%m%d%H%M%S}"
        with st.spinner(f"Creating agent '{agent_id}'..."):
            bigq = geminidataanalytics.BigQueryTableReference(
                project_id=bq_project_id, dataset_id=bq_dataset_id, table_id=bq_table_id
            )
            refs = geminidataanalytics.DatasourceReferences(bq={"table_references": [bigq]})
            ctx = geminidataanalytics.Context(
                system_instruction=system_instruction, datasource_references=refs
            )
            agent = geminidataanalytics.DataAgent(data_analytics_agent={"published_context": ctx})
            req = geminidataanalytics.CreateDataAgentRequest(
                parent=f"projects/{billing_project}/locations/global",
                data_agent_id=agent_id,
                data_agent=agent,
            )
            data_agent_client.create_data_agent(request=req)
            st.session_state["data_agent_id"] = agent_id
            st.toast("Agent created")


    agent_path = f"projects/{billing_project}/locations/global/dataAgents/{st.session_state['data_agent_id']}"


    if not st.session_state.get("conversation_id"):
        convo_id = f"conv_{pd.Timestamp.now():%Y%m%d%H%M%S}"
        with st.spinner(f"Starting conversation '{convo_id}'..."):
            convo = geminidataanalytics.Conversation(agents=[agent_path])
            req = geminidataanalytics.CreateConversationRequest(
                parent=f"projects/{billing_project}/locations/global",
                conversation_id=convo_id,
                conversation=convo,
            )
            data_chat_client.create_conversation(request=req)
            st.session_state["conversation_id"] = convo_id
            st.toast("Conversation started")


    st.session_state.setdefault("messages", [])
    for msg in st.session_state["messages"]:
        role = "user" if msg.get("role") == "user" else "assistant"
        with st.chat_message(role):
            if role == "user":
                st.markdown(msg["content"])
            else:
                render_assistant_message(msg["content"])


    if prompt := st.chat_input("What would you like to know?"):
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                user_msg = geminidataanalytics.Message(user_message={"text": prompt})
                convo_ref = geminidataanalytics.ConversationReference(
                    conversation=f"projects/{billing_project}/locations/global/conversations/{st.session_state['conversation_id']}",
                    data_agent_context={"data_agent": agent_path},
                )
                req = geminidataanalytics.ChatRequest(
                    parent=f"projects/{billing_project}/locations/global",
                    messages=[user_msg],
                    conversation_reference=convo_ref,
                )
                stream = data_chat_client.chat(request=req)
                res = process_chat_stream(stream)
                render_assistant_message(res)
                st.session_state["messages"].append({"role": "assistant", "content": res})



with tab2:
    st.header("Data Agent Management")
    if st.button("List and Show Agent Details"):
        with st.spinner("Fetching agents..."):
            try:
                req = geminidataanalytics.ListDataAgentsRequest(parent=f"projects/{billing_project}/locations/global")
                agents = list(data_agent_client.list_data_agents(request=req))
                if not agents: st.info("No agents found.")
                for ag in agents:
                    with st.expander(ag.display_name or ag.name.split('/')[-1]):
                        st.write(f"**Resource:** {ag.name}")
                        if ag.description: st.write(f"**Description:** {ag.description}")
                        st.write(f"**Created:** {ag.create_time}")
                        st.write(f"**Updated:** {ag.update_time}")
            except Exception as e:
                st.error(f"Fetch error: {e}")

with tab3:
    st.header("Conversation History")
    if SESSION_AGENTS_MAP not in st.session_state:
        st.session_state[SESSION_AGENTS_MAP] = {}
    if SESSION_CONVERSATIONS not in st.session_state:
        st.session_state[SESSION_CONVERSATIONS] = []
    if st.button("Load Conversations"):
        with st.spinner("Loading..."):
            try:
                agents = list(data_agent_client.list_data_agents(parent=f"projects/{billing_project}/locations/global"))
                st.session_state[SESSION_AGENTS_MAP] = {a.name: a for a in agents}
                st.session_state[SESSION_CONVERSATIONS] = list(data_chat_client.list_conversations(parent=f"projects/{billing_project}/locations/global"))
            except Exception as e:
                st.error(f"Load error: {e}")
    for conv in st.session_state[SESSION_CONVERSATIONS]:
        title = conv.name.split('/')[-1]
        with st.expander(f"Conversation: {title}"):
            st.write(f"Last Used: {conv.last_used_time}")
            if st.button(f"View {title}", key=title):
                with st.spinner("Fetching messages..."):
                    try:
                        msgs = list(data_chat_client.list_messages(parent=conv.name))
                        for m in msgs:
                            if getattr(m, 'user_message', None):
                                with st.chat_message(CHAT_ROLE_USER): st.markdown(m.user_message.text)
                            else:
                                with st.chat_message(CHAT_ROLE_ASSISTANT): render_assistant_message(process_chat_stream([m]))
                    except Exception as e:
                        st.error(f"Message load error: {e}")

with tab4:
    st.header("Update Data Agent")
    agent_id = st.text_input("Agent ID to update", key="update_agent_id")
    desc = st.text_area("New description", key="update_desc")
    if st.button("Update Agent"):
        try:
            path = data_agent_client.data_agent_path(billing_project, "global", agent_id)
            agent = geminidataanalytics.DataAgent(name=path, description=desc)
            mask = field_mask_pb2.FieldMask(paths=['description'])
            data_agent_client.update_data_agent(agent=agent, update_mask=mask)
            st.success("Updated")
        except Exception as e:
            st.error(f"Update error: {e}")
