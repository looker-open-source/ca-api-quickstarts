import os
import pandas as pd
import proto
import streamlit as st
import google.auth
from datetime import datetime
from dotenv import load_dotenv
from streamlit_cookies_manager import EncryptedCookieManager
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import geminidataanalytics
from google.protobuf.json_format import MessageToDict
import altair as alt

from app_secrets import get_secret
from auth import Authenticator
from error_handling import handle_streamlit_exception

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Chat with your data",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)
hide_streamlit_style = """
<style>
.css-hi6a2p {padding-top: 0rem;}
</style>

"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- GLOBAL CSS ---
st.markdown(
    """
<style>
  :root {
    --sidebar-width: 18rem;
    --page-padding: 1rem;
    --chat-input-border-color: #28a745;
  }
  div.block-container {padding-top: 1rem;}
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
  [data-testid="stVerticalBlock"] {padding-bottom: 6rem !important;}
</style>
""",
    unsafe_allow_html=True,
)

# --- LOAD .env ---
load_dotenv()

# --- AUTH ---
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

if "auth_token_info" not in st.session_state or st.session_state["auth_token_info"] is None:
    st.error("Login succeeded but token info missing; please re-authenticate.")
    st.stop()

# Refresh token
creds = st.session_state.get("creds")
if creds and creds.refresh_token:
    try:
        creds.refresh(GoogleAuthRequest())
        st.session_state["auth_token_info"]["access_token"] = creds.token
        st.session_state["auth_token_info"]["expiry"] = creds.expiry.isoformat()
        auth._save_token_to_firestore(
            st.session_state["user_email"],
            st.session_state["auth_token_info"],
        )
    except Exception as e:
        st.error(f"Could not refresh credentials: {e}")
        st.stop()

# Client setup
data_agent_client = geminidataanalytics.DataAgentServiceClient(credentials=creds)
data_chat_client  = geminidataanalytics.DataChatServiceClient(credentials=creds)

# Suggested questions
SUGGESTED_QUESTIONS = {
    ("faa","us_airports"): [
        "What are the highest and lowest elevation airports in the United States? ✈️",
        "Which states have airports in multiple timezones? 🕒",
        "What is the northernmost, southernmost, easternmost, and westernmost airport in the contiguous United States? 🧭"
    ]
}

def handle_suggestion_click(question):
    st.session_state["prompt_from_suggestion"] = question


# Helper: convert proto to dict
def _convert_proto_to_dict(msg):
    if isinstance(msg, proto.marshal.collections.maps.MapComposite):
        return {k: _convert_proto_to_dict(v) for k,v in msg.items()}
    if isinstance(msg, proto.marshal.collections.RepeatedComposite):
        return [_convert_proto_to_dict(x) for x in msg]
    if isinstance(msg,(int,float,str,bool)):
        return msg
    return MessageToDict(msg,preserving_proto_field_name=True)

# --- HEADER & USER INFO ---
user_info = {
    "name": st.session_state["auth_token_info"].get("id_token_claims",{}).get("name"),
    "email": st.session_state["auth_token_info"].get("email"),
    "picture": st.session_state["auth_token_info"].get("id_token_claims",{}).get("picture"),
}
col1,col2=st.columns([5,1])
with col1:
    st.title("Chat with your data")
with col2:
    with st.popover(f"👤 {user_info['name']}",use_container_width=True):
        if user_info.get("picture"): st.image(user_info["picture"],width=80)
        st.markdown(f"**{user_info['name']}**")
        st.caption(user_info['email'])
        st.divider()
        if st.button("Logout",use_container_width=True):
            auth._clear_token_from_firestore(st.session_state['user_email'])
            cookies['user_email']=''
            for k in ['user_email','auth_token_info','creds']: st.session_state.pop(k,None)
            st.rerun()

# Sidebar settings
st.sidebar.header("Settings")
billing_project = st.sidebar.text_input("GCP Billing Project ID",google.auth.default()[1],key='billing_project')



bq_project_id = st.sidebar.text_input(
    "BQ Project ID", "bigquery-public-data", key="bq_project_id"
)
bq_dataset_id = st.sidebar.text_input(
    "BQ Dataset ID", "faa", key="bq_dataset_id"
)
bq_table_id = st.sidebar.text_input(
    "BQ Table ID", "us_airports", key="bq_table_id"
)

user_system_instruction = st.sidebar.text_area(
    "Agent Instructions", value="", key="system_instruction", height=200
)
if st.sidebar.button("Clear Chat 🧹"):
    st.session_state["messages"] = []
    st.rerun()

# --- MAIN: CHAT ---
if not all([billing_project, bq_project_id, bq_dataset_id, bq_table_id]):
    st.warning("👋 Please complete all GCP and BigQuery details in the sidebar.")
    st.stop()

# Create agent
if "data_agent_id" not in st.session_state:
    agent_id = f"agent_{pd.Timestamp.now():%Y%m%d%H%M%S}"
    with st.spinner(f"Creating agent '{agent_id}'..."):
        bigq = geminidataanalytics.BigQueryTableReference(
            project_id=bq_project_id, dataset_id=bq_dataset_id, table_id=bq_table_id
        )
        refs = geminidataanalytics.DatasourceReferences(bq={"table_references": [bigq]})
        ctx = geminidataanalytics.Context(
            system_instruction=user_system_instruction,
            datasource_references=refs,
        )
        agent = geminidataanalytics.DataAgent(data_analytics_agent={"published_context": ctx})
        req = geminidataanalytics.CreateDataAgentRequest(
            parent=f"projects/{billing_project}/locations/global",
            data_agent_id=agent_id,
            data_agent=agent,
        )
        data_agent_client.create_data_agent(request=req)
        st.session_state.data_agent_id = agent_id

# Create conversation
if "conversation_id" not in st.session_state:
    convo_id = f"conv_{pd.Timestamp.now():%Y%m%d%H%M%S}"
    with st.spinner(f"Starting conversation '{convo_id}'..."):
        convo = geminidataanalytics.Conversation(
            agents=[f"projects/{billing_project}/locations/global/dataAgents/{st.session_state.data_agent_id}"]
        )
        req = geminidataanalytics.CreateConversationRequest(
            parent=f"projects/{billing_project}/locations/global",
            conversation_id=convo_id,
            conversation=convo,
        )
        data_chat_client.create_conversation(request=req)
        st.session_state.conversation_id = convo_id

# Suggested questions
dataset_ref = f"{bq_project_id}.{bq_dataset_id}.{bq_table_id}"
st.markdown(f"##### Suggested Questions for `{dataset_ref}`")
questions = SUGGESTED_QUESTIONS.get((bq_dataset_id, bq_table_id), [])
if questions:
    cols = st.columns(len(questions))
    for i, q in enumerate(questions):
        with cols[i]:
            st.button(q, on_click=handle_suggestion_click, args=(q,), use_container_width=True)
else:
    st.info("No suggested questions for this dataset.")

# Chat history
if "messages" not in st.session_state:
    st.session_state["messages"] = []
for msg in st.session_state["messages"]:
    role = msg.get("role", "assistant")
    with st.chat_message(role):
        if role == "user":
            st.markdown(msg.get("content", ""))
        else:
            render_assistant_message(msg.get("content", {}))

# Chat input
prompt = st.session_state.pop("prompt_from_suggestion", None)
user_input = st.chat_input("What would you like to know?")
if user_input:
    prompt = user_input

if prompt:
    # Record user message
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Assistant response
    with st.chat_message("assistant"):
        full_summary = ""
        final_sql = ""
        all_dfs = []
        has_chart = False
        with st.spinner("Thinking... 🤖"):
            user_msg = geminidataanalytics.Message(user_message={"text": prompt})
            convo_ref = geminidataanalytics.ConversationReference(
                conversation=f"projects/{billing_project}/locations/global/conversations/{st.session_state['conversation_id']}",
                data_agent_context={"data_agent": f"projects/{billing_project}/locations/global/dataAgents/{st.session_state['data_agent_id']}"},
            )
            req = geminidataanalytics.ChatRequest(
                parent=f"projects/{billing_project}/locations/global",
                messages=[user_msg],
                conversation_reference=convo_ref,
            )
            for response in data_chat_client.chat(request=req):
                m = response.system_message
                if getattr(m, "text", None) and m.text.parts:
                    full_summary += "".join(m.text.parts)
                if getattr(m, "data", None):
                    if m.data.generated_sql:
                        final_sql = m.data.generated_sql
                    rows = getattr(m.data.result, "data", []) or []
                    if rows:
                        df_chunk = pd.DataFrame([_convert_proto_to_dict(r) for r in rows])
                        all_dfs.append(df_chunk)
                if getattr(m, "chart", None):
                    has_chart = True
        final_df = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
        content = {
            "summary": full_summary,
            "sql": final_sql,
            "dataframe": final_df,
            "has_chart": has_chart,
        }
        render_assistant_message(content)
        # Store assistant message
        st.session_state["messages"].append({"role": "assistant", "content": content})
        st.rerun()
