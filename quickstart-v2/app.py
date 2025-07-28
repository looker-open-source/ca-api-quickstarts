from streamlit_cookies_manager import EncryptedCookieManager
import os
import uuid
import traceback
import altair as alt
import pandas as pd
import proto
import streamlit as st
import google.auth
from dotenv import load_dotenv
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import geminidataanalytics
from google.protobuf import field_mask_pb2
from google.protobuf.json_format import MessageToDict
from app_secrets import get_secret
from auth import Authenticator
from error_handling import (
    log_error,
    log_user_login,
    log_user_logout,
    handle_errors,
    handle_streamlit_exception,
)
import json as json_lib


os.environ["GRPC_POLL_STRATEGY"] = "poll"

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Conversational Analytics API",
    page_icon="🗣️",
    layout="wide",
    initial_sidebar_state="expanded",
)
load_dotenv()

# --- DATA FOR SUGGESTED QUESTIONS ---
SUGGESTED_QUESTIONS = {
    ("faa", "us_airports"): [
        "What are the highest and lowest elevation airports in the United States? ✈️",
        "Which states have airports in multiple timezones? 🕒",
        "What is the northernmost, southernmost, easternmost, and westernmost airport in the contiguous United States? 🧭",
    ],
    ("google_trends", "top_terms"): [
        "What are the top 10 search terms of the week? 📈",
        "Which search term has the highest rank? 🏆",
        "Show me the top search terms for each day of the week. 📅",
    ],
}

# --- HELPER FUNCTIONS ---

@st.cache_data
def get_default_project_id():
    """Tries to get the default GCP Project ID from the environment."""
    try:
        _, project_id = google.auth.default()
        return project_id
    except google.auth.exceptions.DefaultCredentialsError:
        return None
    except Exception as e:
        handle_streamlit_exception(e, "get_default_project_id")

def _convert_proto_to_dict(msg):
    """Recursively converts a proto message to a dictionary."""
    if isinstance(msg, proto.marshal.collections.maps.MapComposite):
        return {k: _convert_proto_to_dict(v) for k, v in msg.items()}
    if isinstance(msg, proto.marshal.collections.RepeatedComposite):
        return [_convert_proto_to_dict(x) for x in msg]
    if isinstance(msg, (int, float, str, bool)):
        return msg
    return MessageToDict(msg, preserving_proto_field_name=True)

def _convert_history_message_to_dict(msg):
    """Converts a single historical message proto into a dict for rendering."""
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
    return {
        "sql": gen_sql, "dataframe": df,
        "summary": summary, "has_chart": has_chart,
    }

def handle_suggestion_click(question):
    """Callback function to handle suggested question button clicks."""
    st.session_state.prompt_from_suggestion = question

# --- STREAMING RESPONSE HANDLERS ---

def handle_text_response(resp):
    """Renders streaming text directly to the page."""
    text = "".join(resp.parts)
    st.markdown(text, unsafe_allow_html=True)
    return text

def handle_data_response(resp):
    """Renders SQL and returns the resulting DataFrame."""
    gen_sql, df = "", pd.DataFrame()
    if resp.generated_sql:
        gen_sql = resp.generated_sql
        with st.expander("Show Generated SQL"):
            st.code(gen_sql, language="sql")
    if getattr(resp.result, "data", []):
        rows = resp.result.data
        df = pd.DataFrame(
            [_convert_proto_to_dict(r) for r in rows],
            columns=[f.name for f in resp.result.schema.fields],
        )
    return gen_sql, df

def show_message(msg):
    """Dispatcher function to call the correct handler for a streamed message."""
    m = msg.system_message
    summary_chunk, sql_chunk, df_chunk = "", "", pd.DataFrame()
    if "text" in m:
        summary_chunk = handle_text_response(m.text)
    elif "data" in m:
        sql_chunk, df_chunk = handle_data_response(m.data)
    return summary_chunk, sql_chunk, df_chunk

def render_assistant_message(content):
    """Renders a complete, non-streamed assistant message for history."""
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

# --- MAIN APP LAYOUT AND STYLE ---

st.markdown(
    """
<style>
  :root {
    --sidebar-width: 18rem;
    --page-padding: 1rem;
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
    border: 2px solid #28a745 !important;
    border-radius: 8px !important;
  }
  [data-testid="stVerticalBlock"] {
    padding-bottom: 6rem !important;
  }
</style>
""",
    unsafe_allow_html=True,
)

# --- CONSTANTS ---
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

# --- AUTH & CLIENT SETUP ---
cookies = EncryptedCookieManager(password="fVfYQc3B6XT52_23337588")
if not cookies.ready():
    st.info("Cookies not ready...pausing....")
    st.stop()

auth = Authenticator(cookies)
auth.check_session()

if not st.session_state.get("user_email"):
    auth.login_widget()
    st.stop()

if "auth_token_info" not in st.session_state or st.session_state["auth_token_info"] is None:
    st.error("Login succeeded but token info missing; please re-authenticate.")
    st.stop()

token_info = st.session_state["auth_token_info"]
credentials = st.session_state.get(SESSION_CREDS)
user_info = {
    "email": token_info.get("email"),
    "name": token_info.get("id_token_claims", {}).get("name", token_info.get("email")),
    "picture": token_info.get("id_token_claims", {}).get("picture"),
}
if credentials and credentials.expired and credentials.refresh_token:
    credentials.refresh(GoogleAuthRequest())

data_agent_client = geminidataanalytics.DataAgentServiceClient(credentials=credentials)
data_chat_client = geminidataanalytics.DataChatServiceClient(credentials=credentials)

st.session_state.setdefault(SESSION_MESSAGES, [])
st.session_state.setdefault(SESSION_CONVERSATION_ID, None)
st.session_state.setdefault(SESSION_DATA_AGENT_ID, None)


# --- SIDEBAR ---
if user_info.get(USER_INFO_PICTURE):
    st.sidebar.image(user_info[USER_INFO_PICTURE], width=100)
st.sidebar.write(f"**Name:** {user_info.get(USER_INFO_NAME)}")
st.sidebar.write(f"**Email:** {user_info.get(USER_INFO_EMAIL)}")
if st.sidebar.button("Logout"):
    user_email = st.session_state.get("user_email")
    if user_email:
        auth._clear_token_from_firestore(user_email)
        auth.cookies["user_email"] = ""
    for key in ["user_email", "auth_token_info", "creds"]:
        st.session_state.pop(key, None)
    st.rerun()

st.sidebar.divider()
st.sidebar.markdown("Enter your GCP project and BigQuery source below.")
billing_project = st.sidebar.text_input(
    "GCP Billing Project ID", get_default_project_id(), key=WIDGET_BILLING_PROJECT
)

bq_sources = {
    "bigquery-public-data": {
        "faa": ["us_airports"],
        "gbif": ["occurrences"],
        "google_trends": ["top_terms"],
    }
}
default_project = "bigquery-public-data"
default_dataset = "faa"
default_table = "us_airports"

with st.sidebar.expander("BigQuery Data Source", expanded=True):
    project_list = list(bq_sources.keys())
    project_index = project_list.index(default_project) if default_project in project_list else 0
    bq_project_id = st.selectbox(
        "BQ Project ID", project_list, index=project_index, key=WIDGET_BQ_PROJECT_ID
    )
    dataset_list = list(bq_sources.get(bq_project_id, {}).keys())
    dataset_index = dataset_list.index(default_dataset) if default_dataset in dataset_list else 0
    bq_dataset_id = st.selectbox(
        "BQ Dataset ID", dataset_list, index=dataset_index, key=WIDGET_BQ_DATASET_ID
    )
    table_list = bq_sources.get(bq_project_id, {}).get(bq_dataset_id, [])
    table_index = table_list.index(default_table) if default_table in table_list else 0
    bq_table_id = st.selectbox(
        "BQ Table ID", table_list, index=table_index, key=WIDGET_BQ_TABLE_ID
    )
    
    if (
        st.session_state.get(SESSION_PREV_BQ_PROJECT_ID) != bq_project_id
        or st.session_state.get(SESSION_PREV_BQ_DATASET_ID) != bq_dataset_id
        or st.session_state.get(SESSION_PREV_BQ_TABLE_ID) != bq_table_id
    ):
        st.session_state.update(
            {
                SESSION_DATA_AGENT_ID: None,
                SESSION_CONVERSATION_ID: None,
                SESSION_MESSAGES: [],
                SESSION_PREV_BQ_PROJECT_ID: bq_project_id,
                SESSION_PREV_BQ_DATASET_ID: bq_dataset_id,
                SESSION_PREV_BQ_TABLE_ID: bq_table_id,
            }
        )
        st.rerun()

with st.sidebar.expander("System Instructions", expanded=True):
    system_instruction = st.text_area(
        label="Agent Instructions",
        value="""When a user asks for both the highest/maximum and lowest/minimum of a value, you MUST return both the top and bottom records. Use a UNION ALL statement to combine the two queries. Also, only render a chart or visualization if the user specifically asks for one.""",
        key=WIDGET_SYSTEM_INSTRUCTION,
        height=200,
    )

st.title("Conversational Analytics API")

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(
    ["Chat", "Data Agent Management", "Conversation History", "Update Data Agent"]
)

with tab1:
    st.header("Ask a question below...")
    if not all([billing_project, bq_project_id, bq_dataset_id, bq_table_id]):
        st.warning(
            "👋 Please complete all GCP and BigQuery details in the sidebar to activate the chat."
        )
        st.stop()

    # --- AGENT AND CONVERSATION SETUP ---
    if not st.session_state.get(SESSION_DATA_AGENT_ID):
        agent_id = f"agent_{pd.Timestamp.now():%Y%m%d%H%M%S}"
        with st.spinner(f"Creating agent '{agent_id}'..."):
            bigq = geminidataanalytics.BigQueryTableReference(
                project_id=bq_project_id, dataset_id=bq_dataset_id, table_id=bq_table_id
            )
            refs = geminidataanalytics.DatasourceReferences(
                bq={"table_references": [bigq]}
            )
            ctx = geminidataanalytics.Context(
                system_instruction=system_instruction, datasource_references=refs
            )
            agent = geminidataanalytics.DataAgent(
                data_analytics_agent={"published_context": ctx}
            )
            req = geminidataanalytics.CreateDataAgentRequest(
                parent=f"projects/{billing_project}/locations/global",
                data_agent_id=agent_id,
                data_agent=agent,
            )
            data_agent_client.create_data_agent(request=req)
            st.session_state[SESSION_DATA_AGENT_ID] = agent_id
            st.toast("Agent created")

    agent_path = f"projects/{billing_project}/locations/global/dataAgents/{st.session_state[SESSION_DATA_AGENT_ID]}"

    if not st.session_state.get(SESSION_CONVERSATION_ID):
        convo_id = f"conv_{pd.Timestamp.now():%Y%m%d%H%M%S}"
        with st.spinner(f"Starting conversation '{convo_id}'..."):
            convo = geminidataanalytics.Conversation(agents=[agent_path])
            req = geminidataanalytics.CreateConversationRequest(
                parent=f"projects/{billing_project}/locations/global",
                conversation_id=convo_id,
                conversation=convo,
            )
            data_chat_client.create_conversation(request=req)
            st.session_state[SESSION_CONVERSATION_ID] = convo_id
            st.toast("Conversation started")

    # --- SUGGESTED QUESTIONS UI ---
    st.markdown("---")
    st.markdown("##### Suggested Questions")
    questions = SUGGESTED_QUESTIONS.get((bq_dataset_id, bq_table_id), [])
    if questions:
        cols = st.columns(len(questions))
        for i, question in enumerate(questions):
            with cols[i]:
                st.button(
                    question,
                    on_click=handle_suggestion_click,
                    args=(question,),
                    use_container_width=True,
                )
    else:
        st.info("No suggested questions for this dataset.")

    # --- CHAT HISTORY ---
    st.markdown("---")
    for msg in st.session_state[SESSION_MESSAGES]:
        role = "user" if msg.get("role") == "user" else "assistant"
        with st.chat_message(role):
            if role == "user":
                st.markdown(msg["content"])
            else:
                render_assistant_message(msg["content"])
    
    # --- CHAT INPUT AND PROCESSING LOGIC ---
    prompt = None
    if "prompt_from_suggestion" in st.session_state:
        prompt = st.session_state.prompt_from_suggestion
        del st.session_state.prompt_from_suggestion
    
    user_input = st.chat_input("What would you like to know?")
    if user_input:
        prompt = user_input

    if prompt:
        st.session_state[SESSION_MESSAGES].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            full_summary, final_sql, all_dfs = "", "", []
            with st.spinner("Thinking..."):
                user_msg = geminidataanalytics.Message(user_message={"text": prompt})
                convo_ref = geminidataanalytics.ConversationReference(
                    conversation=f"projects/{billing_project}/locations/global/conversations/{st.session_state[SESSION_CONVERSATION_ID]}",
                    data_agent_context={"data_agent": agent_path},
                )
                req = geminidataanalytics.ChatRequest(
                    parent=f"projects/{billing_project}/locations/global",
                    messages=[user_msg],
                    conversation_reference=convo_ref,
                )
                stream = data_chat_client.chat(request=req)

            st.write("#### Assistant's Thought Process")
            for response in stream:
                summary_chunk, sql_chunk, df_chunk = show_message(response)
                if summary_chunk:
                    full_summary += summary_chunk
                if sql_chunk:
                    final_sql = sql_chunk
                if not df_chunk.empty:
                    all_dfs.append(df_chunk)

            st.markdown("---")
            st.write("#### Final Answer")
            if all_dfs:
                final_df = pd.concat(all_dfs, ignore_index=True)
                st.dataframe(final_df)
                res = {
                    RESULT_SUMMARY: full_summary,
                    RESULT_SQL: final_sql,
                    RESULT_DATAFRAME: final_df,
                    RESULT_HAS_CHART: False,
                }
                st.session_state[SESSION_MESSAGES].append(
                    {"role": "assistant", "content": res}
                )
            else:
                st.markdown(full_summary)
                res = {
                    RESULT_SUMMARY: full_summary,
                    RESULT_SQL: "",
                    RESULT_DATAFRAME: pd.DataFrame(),
                    RESULT_HAS_CHART: False,
                }
                st.session_state[SESSION_MESSAGES].append(
                    {"role": "assistant", "content": res}
                )
            st.rerun()

with tab2:
    st.header("Data Agent Management")
    if st.button("List and Show Agent Details"):
        with st.spinner("Fetching agents..."):
            try:
                req = geminidataanalytics.ListDataAgentsRequest(
                    parent=f"projects/{billing_project}/locations/global"
                )
                agents = list(data_agent_client.list_data_agents(request=req))
                if not agents:
                    st.info("No agents found.")
                for ag in agents:
                    with st.expander(ag.display_name or ag.name.split("/")[-1]):
                        st.write(f"**Resource:** {ag.name}")
                        if ag.description:
                            st.write(f"**Description:** {ag.description}")
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
                agents = list(
                    data_agent_client.list_data_agents(
                        parent=f"projects/{billing_project}/locations/global"
                    )
                )
                st.session_state[SESSION_AGENTS_MAP] = {a.name: a for a in agents}
                st.session_state[SESSION_CONVERSATIONS] = list(
                    data_chat_client.list_conversations(
                        parent=f"projects/{billing_project}/locations/global"
                    )
                )
            except Exception as e:
                st.error(f"Load error: {e}")
    for conv in st.session_state[SESSION_CONVERSATIONS]:
        title = conv.name.split("/")[-1]
        with st.expander(f"Conversation: {title}"):
            st.write(f"Last Used: {conv.last_used_time}")
            if st.button(f"View {title}", key=title):
                with st.spinner("Fetching messages..."):
                    try:
                        msgs = list(data_chat_client.list_messages(parent=conv.name))
                        for m in msgs:
                            role = (
                                "user"
                                if getattr(m, "user_message", None)
                                else "assistant"
                            )
                            with st.chat_message(role):
                                if role == "user":
                                    st.markdown(m.user_message.text)
                                else:
                                    render_assistant_message(
                                        _convert_history_message_to_dict(m)
                                    )
                    except Exception as e:
                        st.error(f"Message load error: {e}")

with tab4:
    st.header("Update Data Agent")
    agent_id = st.text_input("Agent ID to update", key="update_agent_id")
    desc = st.text_area("New description", key="update_desc")
    if st.button("Update Agent"):
        try:
            path = data_agent_client.data_agent_path(
                billing_project, "global", agent_id
            )
            agent = geminidataanalytics.DataAgent(name=path, description=desc)
            mask = field_mask_pb2.FieldMask(paths=["description"])
            data_agent_client.update_data_agent(agent=agent, update_mask=mask)
            st.success("Updated")
        except Exception as e:
            st.error(f"Update error: {e}")