# --- START FILE: pages/1_Chat_with_data.py ---
import os
import getpass
from datetime import datetime
from google.protobuf.message import Message as PbMessage  # optional, for classic protos
import altair as alt
import google.auth
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import geminidataanalytics
from google.protobuf.json_format import MessageToDict
from streamlit_extras.add_vertical_space import add_vertical_space
from error_handling import handle_errors


# ---------- ADC helpers ----------
def get_adc_credentials(scopes=None):
    creds, project = google.auth.default(scopes=scopes)
    if not creds.valid:
        creds.refresh(GoogleAuthRequest())
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or project
    return creds, project




@handle_errors
def chat_part_one():
    # --- PAGE CONFIG ---
    st.set_page_config(
        page_title="Chat with your data",
        page_icon="💬",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .block-container { padding-top: 0rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --- GLOBAL CSS (keep your centered chat input) ---
    st.markdown(
        """
        <style>
        :root { --sidebar-width: 18rem; --page-padding: 1rem; --chat-input-border-color: #28a745; }
        div.block-container {padding-top: 1rem;}
        [data-testid="stChatInputContainer"], [data-testid="stChatInput"] {
            position: fixed !important; bottom: 0 !important; left: 50% !important;
            transform: translateX(-50%) !important; width: 50vw !important;
            max-width: calc(100vw - var(--sidebar-width) - var(--page-padding)*2) !important;
            background: #fff !important; padding: 0.75rem 1rem !important;
            box-shadow: 0 -2px 8px rgba(0,0,0,0.1) !important; z-index: 9999 !important;
            border-radius: 8px !important;
        }
        [data-testid="stVerticalBlock"] {padding-bottom: 6rem !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    load_dotenv()

    # --- ADC (single source of truth) ---
    SCOPES = [
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/bigquery",
    ]
    creds, project_id = get_adc_credentials(SCOPES)
    st.session_state["adc_credentials"] = creds
    st.session_state["gcp_project_id"] = project_id

    # --- Header: left title + right chip ---
    st.markdown(
            """
            <style>
            h1 {
                margin-bottom: 0rem !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns([5, 1])
    with col1:
        add_vertical_space(5)
        st.title("Chat with your data")


    with col2:
        os_user = getpass.getuser()
        if os_user:
            with st.popover(f"👤 {os_user}", use_container_width=True, help="Click here to logout."):
                st.markdown(f"**{os_user} authenticated with Application Default Credentials**")

    # --- Clients (credentials forwarded) ---
    data_agent_client = geminidataanalytics.DataAgentServiceClient(credentials=creds)
    data_chat_client = geminidataanalytics.DataChatServiceClient(credentials=creds)

    SUGGESTED_QUESTIONS = {
        ("faa", "us_airports"): [
            "What are the highest and lowest elevation airports in the United States,\nincluding the state, county, and city? ✈️",
            "Which states have airports in multiple timezones? 🕒",
            "What is the northernmost, southernmost, easternmost, and westernmost airport in the contiguous United States? 🧭",
        ]
    }

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

    def handle_suggestion_click(question):
        st.session_state["prompt_from_suggestion"] = question


    def safe_to_dict(obj):
        to_dict = getattr(obj, "to_dict", None)
        if callable(to_dict):
            return to_dict()

        if isinstance(obj, PbMessage):
            from google.protobuf.json_format import MessageToDict
            return MessageToDict(obj, preserving_proto_field_name=True)

        if hasattr(obj, "items"):
            return {k: safe_to_dict(v) for k, v in obj.items()}

        if isinstance(obj, (list, tuple)):
            return [safe_to_dict(v) for v in obj]

        return obj


    # Sidebar settings
    @st.cache_data
    def get_default_project_id():
        try:
            _, pid = google.auth.default()
            return os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or pid
        except Exception:
            return None

    st.sidebar.header("Settings")
    billing_project = st.sidebar.text_input(
        "GCP Billing Project ID", get_default_project_id(), key="billing_project"
    )
    bq_project_id = st.sidebar.text_input(
        "BQ Project ID", "bigquery-public-data", key="bq_project_id"
    )
    bq_dataset_id = st.sidebar.text_input("BQ Dataset ID", "faa", key="bq_dataset_id")
    bq_table_id = st.sidebar.text_input("BQ Table ID", "us_airports", key="bq_table_id")

    user_system_instruction = st.sidebar.text_area(
        "Agent Instructions", value="", key="system_instruction", height=200
    ) + " Do not render any visualization unless explicitly asked to"
    if st.sidebar.button("Clear Chat 🧹"):
        st.session_state["messages"] = []
        st.rerun()

    if not all([billing_project, bq_project_id, bq_dataset_id, bq_table_id]):
        st.warning("👋 Please complete all GCP and BigQuery details in the sidebar.")
        st.stop()

    if "data_agent_id" not in st.session_state:
        agent_id = f"agent_{pd.Timestamp.now():%Y%m%d%H%M%S}"
        with st.spinner(f"Creating agent '{agent_id}'..."):
            bigq = geminidataanalytics.BigQueryTableReference(
                project_id=bq_project_id, dataset_id=bq_dataset_id, table_id=bq_table_id
            )
            refs = geminidataanalytics.DatasourceReferences(
                bq={"table_references": [bigq]}
            )
            ctx = geminidataanalytics.Context(
                system_instruction=user_system_instruction,
                datasource_references=refs,
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
            st.session_state.data_agent_id = agent_id

    # Create conversation (once)
    if "conversation_id" not in st.session_state:
        convo_id = f"conv_{pd.Timestamp.now():%Y%m%d%H%M%S}"
        with st.spinner(f"Starting conversation '{convo_id}'..."):
            convo = geminidataanalytics.Conversation(
                agents=[
                    f"projects/{billing_project}/locations/global/dataAgents/{st.session_state.data_agent_id}"
                ]
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
    add_vertical_space(1)
    questions = SUGGESTED_QUESTIONS.get((bq_dataset_id, bq_table_id), [])
    if questions:
        cols = st.columns(len(questions))
        for i, q in enumerate(questions):
            with cols[i]:
                st.button(
                    q,
                    on_click=handle_suggestion_click,
                    args=(q,),
                    use_container_width=True,
                )
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
                    data_agent_context={
                        "data_agent": f"projects/{billing_project}/locations/global/dataAgents/{st.session_state['data_agent_id']}"
                    },
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
                            df_chunk = pd.DataFrame([safe_to_dict(r) for r in rows])
                            all_dfs.append(df_chunk)
                    if getattr(m, "chart", None):
                        has_chart = True
            final_df = (
                pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
            )
            content = {
                "summary": full_summary,
                "sql": final_sql,
                "dataframe": final_df,
                "has_chart": has_chart,
            }
            render_assistant_message(content)
            st.session_state["messages"].append(
                {"role": "assistant", "content": content}
            )
            st.rerun()


chat_part_one()

