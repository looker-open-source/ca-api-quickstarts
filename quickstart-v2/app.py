import json
import os
import traceback

import altair as alt
import google.api_core.exceptions
import pandas as pd
import proto
import streamlit as st
from dotenv import load_dotenv
from google.cloud import geminidataanalytics
from google.protobuf import field_mask_pb2
from google.protobuf.json_format import MessageToDict

from auth_utils import access_secret_version, handle_authentication
from log_utils import log_error, log_user_login, handle_streamlit_exception, handle_errors

# --- Page and Style Configuration ---
st.set_page_config(
    page_title="Conversational Analytics API",
    page_icon="https://lh5.googleusercontent.com/h3jO5QoL0KNkqZMm_TAlWK-mdD4z4Mgbpaa3sTMXHN11CcNjZdSgJ5TknXC6_bpyjr_m7rcTvilUIJAi0qlmF4QxMkV1ElqHCECNJ9XDQGtpkwcqDjW76kE5yB4UV4DBu0LfyTtTceNCTxq4KruQnRQ0sDGtSvr1RboF25vB3bTxfbjYmsDPDQ=w1280",
    layout="wide",
    initial_sidebar_state="expanded",
)
load_dotenv()

st.markdown(
    """
<style>
    .reportview-container { background: #f0f2f6; }
    .sidebar .sidebar-content { background: #ffffff; }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
    }
    .stTextInput>div>div>input { background-color: #ffffff; }
    h1, h2, h3 { color: #1a1a1a; }
</style>
""",
    unsafe_allow_html=True,
)

# --- Constants ---

# Widget Keys (for st.text_input, etc.)
WIDGET_BILLING_PROJECT = "billing_project"
WIDGET_BQ_PROJECT_ID = "bq_project_id"
WIDGET_BQ_DATASET_ID = "bq_dataset_id"
WIDGET_BQ_TABLE_ID = "bq_table_id"
WIDGET_SYSTEM_INSTRUCTION = "system_instruction"
WIDGET_CONVO_SEARCH = "convo_search"

SESSION_LOGGED_IN = "logged_in"
SESSION_TOKEN = "token"
SESSION_CREDS = "creds"
SESSION_USER_INFO = "user_info"
SESSION_USER_ID = "user_id"
SESSION_MESSAGES = "messages"
SESSION_CONVERSATION_ID = "conversation_id"
SESSION_DATA_AGENT_ID = "data_agent_id"
SESSION_PREV_BQ_PROJECT_ID = "prev_bq_project_id"
SESSION_PREV_BQ_DATASET_ID = "prev_bq_dataset_id"
SESSION_PREV_BQ_TABLE_ID = "prev_bq_table_id"
SESSION_AGENTS_MAP = "all_agents_map"
SESSION_CONVERSATIONS = "all_conversations"


# Dictionary and Token Keys
USER_INFO_EMAIL = "email"
USER_INFO_NAME = "name"
USER_INFO_PICTURE = "picture"

# Chat Message Structure Keys
CHAT_ROLE = "role"
CHAT_CONTENT = "content"
CHAT_ROLE_USER = "user"
CHAT_ROLE_ASSISTANT = "assistant"

# Processed API Result Keys
RESULT_SQL = "sql"
RESULT_DATAFRAME = "dataframe"
RESULT_SUMMARY = "summary"
RESULT_HAS_CHART = "has_chart"


# --- Top-Level Helper to Convert Protobuf to Dict ---
def _convert_proto_to_dict(proto_message):
    """Recursively converts a Protobuf message to a dictionary."""
    if isinstance(proto_message, proto.marshal.collections.maps.MapComposite):
        return {k: _convert_proto_to_dict(v) for k, v in proto_message.items()}
    elif isinstance(proto_message, proto.marshal.collections.RepeatedComposite):
        return [_convert_proto_to_dict(el) for el in proto_message]
    elif isinstance(proto_message, (int, float, str, bool)):
        return proto_message
    else:
        return MessageToDict(proto_message, preserving_proto_field_name=True)


# --- Main Application ---
is_logged_in = handle_authentication()

if is_logged_in:
    log_user_login(st.session_state[SESSION_USER_INFO][USER_INFO_EMAIL])
    credentials = st.session_state[SESSION_CREDS]
    data_agent_client = geminidataanalytics.DataAgentServiceClient(
        credentials=credentials
    )
    data_chat_client = geminidataanalytics.DataChatServiceClient(
        credentials=credentials
    )
    st.session_state.setdefault(SESSION_MESSAGES, [])
    st.session_state.setdefault(SESSION_CONVERSATION_ID, None)
    st.session_state.setdefault(SESSION_DATA_AGENT_ID, None)

    @handle_errors
    def process_chat_stream(stream):
        generated_sql, summary_text = "", ""
        df = pd.DataFrame()
        has_chart_signal = False

        for response in stream:
            m = response.system_message
            if hasattr(m, "data") and m.data:
                if m.data.generated_sql:
                    generated_sql = m.data.generated_sql
                if (
                    hasattr(m.data, "result")
                    and hasattr(m.data.result, "schema")
                    and hasattr(m.data.result, "data")
                    and len(m.data.result.data) > 0
                ):
                    fields = [field.name for field in m.data.result.schema.fields]
                    data_rows = [
                        _convert_proto_to_dict(row) for row in m.data.result.data
                    ]
                    df = pd.DataFrame(data_rows, columns=fields)
            elif hasattr(m, "text") and m.text and m.text.parts:
                summary_text += "".join(m.text.parts)

            if hasattr(m, "chart") and m.chart:
                has_chart_signal = True

        return {
            RESULT_SQL: generated_sql,
            RESULT_DATAFRAME: df,
            RESULT_SUMMARY: summary_text,
            RESULT_HAS_CHART: has_chart_signal,
        }

    def render_assistant_message(content):
        if content.get(RESULT_SUMMARY):
            st.markdown(content[RESULT_SUMMARY])

        if content.get(RESULT_SQL):
            with st.expander("Show Generated SQL"):
                st.code(content[RESULT_SQL], language="sql")

        df = content.get(RESULT_DATAFRAME)
        if df is not None and not df.empty:
            st.subheader("Data Result")
            st.dataframe(df)

            if content.get(RESULT_HAS_CHART):
                st.subheader("Generated Chart")
                try:
                    if len(df.columns) >= 2:
                        x_col, y_col = df.columns[0], df.columns[1]
                        chart = (
                            alt.Chart(df)
                            .mark_bar()
                            .encode(
                                x=alt.X(
                                    f"{x_col}:N",
                                    sort="-y",
                                    title=x_col.replace("_", " ").title(),
                                ),
                                y=alt.Y(
                                    f"{y_col}:Q", title=y_col.replace("_", " ").title()
                                ),
                                tooltip=list(df.columns),
                            )
                            .properties(
                                title=f"Chart of {y_col.replace('_', ' ').title()} by {x_col.replace('_', ' ').title()}"
                            )
                        )
                        st.altair_chart(chart, use_container_width=True)
                    else:
                        st.warning(
                            "Data does not have enough columns to generate a chart."
                        )
                except Exception as e:
                    st.error(f"Could not generate chart: {e}")

    # --- Sidebar and Configuration. ---
    user_info = st.session_state[SESSION_USER_INFO]
    if user_info.get(USER_INFO_PICTURE):
        st.sidebar.image(
            user_info[USER_INFO_PICTURE], width=100, use_container_width="auto"
        )
    st.sidebar.write(f"**Name:** {user_info.get(USER_INFO_NAME)}")
    st.sidebar.write(f"**Email:** {user_info.get(USER_INFO_EMAIL)}")
    if st.sidebar.button("Logout"):
        logout()
    st.sidebar.divider()
    st.sidebar.markdown("Enter your GCP project and data source details below.")

    billing_project = st.sidebar.text_input(
        "GCP Billing Project ID",
        "bp-steveswalker-solutions-303",
        key=WIDGET_BILLING_PROJECT,
    )

    with st.sidebar.expander("BigQuery Data Source", expanded=True):
        bq_project_id = st.text_input(
            "BQ Project ID", "bigquery-public-data", key=WIDGET_BQ_PROJECT_ID
        )
        bq_dataset_id = st.text_input("BQ Dataset ID", "faa", key=WIDGET_BQ_DATASET_ID)
        bq_table_id = st.text_input(
            "BQ Table ID", "us_airports", key=WIDGET_BQ_TABLE_ID
        )

        if (
            st.session_state.get(SESSION_PREV_BQ_PROJECT_ID) != bq_project_id
            or st.session_state.get(SESSION_PREV_BQ_DATASET_ID) != bq_dataset_id
            or st.session_state.get(SESSION_PREV_BQ_TABLE_ID) != bq_table_id
        ):
            st.session_state[SESSION_DATA_AGENT_ID] = None
            st.session_state[SESSION_CONVERSATION_ID] = None
            st.session_state[SESSION_MESSAGES] = []
            st.session_state[SESSION_PREV_BQ_PROJECT_ID] = bq_project_id
            st.session_state[SESSION_PREV_BQ_DATASET_ID] = bq_dataset_id
            st.session_state[SESSION_PREV_BQ_TABLE_ID] = bq_table_id
            st.rerun()

    with st.sidebar.expander("System Instructions"):
        system_instruction = st.text_area(
            "Agent Instructions",
            "You are a helpful data analyst.",
            height=150,
            key=WIDGET_SYSTEM_INSTRUCTION,
        )

    st.title("Conversational Analytics API")

    # --- UI Tabs ---
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Chat", "Data Agent Management", "Conversation History", "Update Data Agent"]
    )

    with tab1:
        st.header("Ask a question about your data")

        if not st.session_state.get(SESSION_DATA_AGENT_ID):
            agent_id = f"streamlit_agent_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}"
            with st.spinner(f"Creating a temporary Data Agent '{agent_id}'..."):
                try:
                    bigquery_table = geminidataanalytics.BigQueryTableReference(
                        project_id=bq_project_id,
                        dataset_id=bq_dataset_id,
                        table_id=bq_table_id,
                    )
                    data_refs = geminidataanalytics.DatasourceReferences(
                        bq={"table_references": [bigquery_table]}
                    )
                    context = geminidataanalytics.Context(
                        system_instruction=system_instruction,
                        datasource_references=data_refs,
                    )
                    data_agent = geminidataanalytics.DataAgent(
                        data_analytics_agent={"published_context": context}
                    )

                    req = geminidataanalytics.CreateDataAgentRequest(
                        parent=f"projects/{billing_project}/locations/global",
                        data_agent_id=agent_id,
                        data_agent=data_agent,
                    )
                    data_agent_client.create_data_agent(request=req)

                    st.session_state[SESSION_DATA_AGENT_ID] = agent_id
                    st.success(f"Data Agent '{agent_id}' created.")
                except Exception as e:
                    st.error(f"Failed to create Data Agent: {e}")
                    st.stop()

        if not st.session_state.get(SESSION_CONVERSATION_ID):
            convo_id = f"streamlit_convo_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}"
            with st.spinner(f"Starting new conversation '{convo_id}'..."):
                try:
                    agent_path = f"projects/{billing_project}/locations/global/dataAgents/{st.session_state[SESSION_DATA_AGENT_ID]}"
                    convo = geminidataanalytics.Conversation(agents=[agent_path])
                    req = geminidataanalytics.CreateConversationRequest(
                        parent=f"projects/{billing_project}/locations/global",
                        conversation_id=convo_id,
                        conversation=convo,
                    )
                    data_chat_client.create_conversation(request=req)
                    st.session_state[SESSION_CONVERSATION_ID] = convo_id
                    st.success(f"Conversation '{convo_id}' started.")
                except Exception as e:
                    st.error(f"Failed to create conversation: {e}")
                    st.stop()

        for message in st.session_state[SESSION_MESSAGES]:
            with st.chat_message(message[CHAT_ROLE]):
                if message[CHAT_ROLE] == CHAT_ROLE_USER:
                    st.markdown(message[CHAT_CONTENT])
                else:
                    render_assistant_message(message[CHAT_CONTENT])

        if prompt := st.chat_input("What would you like to know?"):
            st.session_state[SESSION_MESSAGES].append(
                {CHAT_ROLE: CHAT_ROLE_USER, CHAT_CONTENT: prompt}
            )
            with st.chat_message(CHAT_ROLE_USER):
                st.markdown(prompt)

            with st.chat_message(CHAT_ROLE_ASSISTANT):
                with st.spinner("Thinking..."):
                    try:
                        user_message = geminidataanalytics.Message(
                            user_message={"text": prompt}
                        )
                        convo_ref = geminidataanalytics.ConversationReference(
                            conversation=f"projects/{billing_project}/locations/global/conversations/{st.session_state[SESSION_CONVERSATION_ID]}",
                            data_agent_context={
                                "data_agent": f"projects/{billing_project}/locations/global/dataAgents/{st.session_state[SESSION_DATA_AGENT_ID]}"
                            },
                        )
                        chat_request = geminidataanalytics.ChatRequest(
                            parent=f"projects/{billing_project}/locations/global",
                            messages=[user_message],
                            conversation_reference=convo_ref,
                        )

                        stream = data_chat_client.chat(request=chat_request)
                        chat_results = process_chat_stream(stream)
                        render_assistant_message(chat_results)
                        st.session_state[SESSION_MESSAGES].append(
                            {CHAT_ROLE: CHAT_ROLE_ASSISTANT, CHAT_CONTENT: chat_results}
                        )

                    except google.api_core.exceptions.PermissionDenied as e:
                        st.error(
                            f"Permission Denied: The authenticated user ({user_info.get(USER_INFO_EMAIL)}) may not have access to the BigQuery table or the billing project. Please check IAM permissions. Full error: {e}"
                        )
                    except Exception as e:
                        st.error(f"An error occurred during the chat: {e}")

    with tab2:
        st.header("Data Agent Management")
        if st.button("List and Show Agent Details"):
            try:
                with st.spinner("Fetching data agents..."):
                    req = geminidataanalytics.ListDataAgentsRequest(
                        parent=f"projects/{billing_project}/locations/global"
                    )
                    agents_list = list(data_agent_client.list_data_agents(request=req))

                    if not agents_list:
                        st.info("No data agents found.")
                    else:
                        for agent in agents_list:
                            title = agent.display_name or agent.name.split("/")[-1]
                            with st.expander(f"**{title}**"):
                                st.write(f"**Full Resource Name:** `{agent.name}`")
                                if agent.description:
                                    st.write(f"**Description:** {agent.description}")
                                st.write(
                                    f"**Created:** {agent.create_time.strftime('%Y-%m-%d %H:%M:%S')}"
                                )
                                st.write(
                                    f"**Last Updated:** {agent.update_time.strftime('%Y-%m-%d %H:%M:%S')}"
                                )
                                context = agent.data_analytics_agent.published_context
                                if context.system_instruction:
                                    st.write("**System Instruction:**")
                                    st.info(context.system_instruction)
                                if context.datasource_references.bq.table_references:
                                    st.write("**Data Source:**")
                                    for (
                                        table
                                    ) in (
                                        context.datasource_references.bq.table_references
                                    ):
                                        st.code(
                                            f"{table.project_id}.{table.dataset_id}.{table.table_id}",
                                            language="sql",
                                        )
            except Exception as e:
                st.error(f"Failed to list data agents: {e}")

    with tab3:
        st.header("Conversation History")

        if SESSION_AGENTS_MAP not in st.session_state:
            st.session_state[SESSION_AGENTS_MAP] = {}
        if SESSION_CONVERSATIONS not in st.session_state:
            st.session_state[SESSION_CONVERSATIONS] = []

        if st.button("Load Conversations for Searching"):
            with st.spinner(
                "Fetching all agents and conversations... This may take a moment."
            ):
                try:
                    agents_req = geminidataanalytics.ListDataAgentsRequest(
                        parent=f"projects/{billing_project}/locations/global"
                    )
                    agents_list = list(
                        data_agent_client.list_data_agents(request=agents_req)
                    )
                    st.session_state[SESSION_AGENTS_MAP] = {
                        agent.name: agent for agent in agents_list
                    }

                    convos_req = geminidataanalytics.ListConversationsRequest(
                        parent=f"projects/{billing_project}/locations/global"
                    )
                    st.session_state[SESSION_CONVERSATIONS] = list(
                        data_chat_client.list_conversations(request=convos_req)
                    )
                except Exception as e:
                    st.error(f"Failed to load data: {e}")

        if st.session_state[SESSION_CONVERSATIONS]:
            search_term = st.text_input(
                "Search by Conversation ID, Agent Name, or Data Source (e.g., 'faa.us_airports')",
                key=WIDGET_CONVO_SEARCH,
            ).lower()

            filtered_convos = []
            if search_term:
                for convo in st.session_state[SESSION_CONVERSATIONS]:
                    match = False
                    if search_term in convo.name.lower():
                        match = True
                    if not match:
                        for agent_name in convo.agents:
                            agent = st.session_state[SESSION_AGENTS_MAP].get(agent_name)
                            if agent:
                                if search_term in agent.display_name.lower():
                                    match = True
                                    break
                                context = agent.data_analytics_agent.published_context
                                for (
                                    table
                                ) in context.datasource_references.bq.table_references:
                                    source_path = f"{table.project_id}.{table.dataset_id}.{table.table_id}"
                                    if search_term in source_path.lower():
                                        match = True
                                        break
                            if match:
                                break
                    if match:
                        filtered_convos.append(convo)
                display_list = filtered_convos
            else:
                display_list = st.session_state[SESSION_CONVERSATIONS]

            st.write(
                f"Displaying **{len(display_list)}** of **{len(st.session_state[SESSION_CONVERSATIONS])}** conversations."
            )

            for conversation in display_list:
                title = conversation.name.split("/")[-1]
                with st.expander(f"**Conversation ID: {title}**"):
                    st.write(
                        f"**Last Used:** {conversation.last_used_time.strftime('%Y-%m-%d %H:%M:%S')}"
                    )

                    for agent_name in conversation.agents:
                        agent = st.session_state[SESSION_AGENTS_MAP].get(agent_name)
                        if agent:
                            st.markdown("---")
                            st.write(f"**Agent Name:** {agent.display_name or 'N/A'}")
                            context = agent.data_analytics_agent.published_context
                            st.write("**Data Source(s):**")
                            for (
                                table
                            ) in context.datasource_references.bq.table_references:
                                st.code(
                                    f"{table.project_id}.{table.dataset_id}.{table.table_id}",
                                    language="text",
                                )

                    if st.button("View Messages", key=f"history_{conversation.name}"):
                        with st.spinner("Loading message history..."):
                            try:
                                messages_req = geminidataanalytics.ListMessagesRequest(
                                    parent=conversation.name
                                )
                                message_history = list(
                                    data_chat_client.list_messages(request=messages_req)
                                )

                                if not message_history:
                                    st.warning(
                                        "No message history was found for this conversation."
                                    )
                                else:
                                    for msg in reversed(message_history):
                                        if (
                                            hasattr(msg, "user_message")
                                            and msg.user_message.text
                                        ):
                                            with st.chat_message(CHAT_ROLE_USER):
                                                st.markdown(msg.user_message.text)
                                        elif hasattr(msg, "system_message"):
                                            with st.chat_message(CHAT_ROLE_ASSISTANT):
                                                sys_msg = msg.system_message
                                                if (
                                                    hasattr(sys_msg, "text")
                                                    and sys_msg.text.parts
                                                ):
                                                    st.markdown(
                                                        "".join(sys_msg.text.parts)
                                                    )
                                                elif (
                                                    hasattr(sys_msg, "data")
                                                    and sys_msg.data.generated_sql
                                                ):
                                                    st.code(
                                                        sys_msg.data.generated_sql,
                                                        language="sql",
                                                    )
                                                    st.info(
                                                        "Data tables are not rendered in history view."
                                                    )
                                                else:
                                                    st.info(
                                                        "Assistant response was a non-text element (e.g., chart)."
                                                    )
                                        else:
                                            st.info(
                                                "An unrecognized message format was found in the history."
                                            )
                                            try:
                                                st.json(_convert_proto_to_dict(msg))
                                            except Exception:
                                                st.text(str(msg))
                            except Exception as e:
                                st.error(f"Could not load message history: {e}")
    with tab4:
        st.header("Update Data Agent")

        billing_project = st.session_state.get("billing_project", "")
        location = "global"
        data_agent_id = st.text_input("Data Agent ID", "data_agent_1")
        new_description = st.text_area(
            "New Description", "This is my new updated description."
        )
        system_instruction = st.text_area("System Instruction (optional)", "")

        # UI for BigQuery Table Reference
        bq_project = st.text_input("BigQuery Project", "")
        bq_dataset = st.text_input("BigQuery Dataset", "")
        bq_table = st.text_input("BigQuery Table", "")

        if st.button("Update Data Agent"):
            try:
                # Build the BigQueryTableReference if details are provided
                bigquery_table_reference = None
                if bq_project and bq_dataset and bq_table:
                    bigquery_table_reference = (
                        geminidataanalytics.BigQueryTableReference(
                            project_id=bq_project,
                            dataset_id=bq_dataset,
                            table_id=bq_table,
                        )
                    )
                    datasource_references = geminidataanalytics.DatasourceReferences(
                        bq=geminidataanalytics.BigQueryTableReferences(
                            table_references=[bigquery_table_reference]
                        )
                    )
                else:
                    datasource_references = None  # or skip this arg if not needed

                published_context = geminidataanalytics.Context(
                    system_instruction=system_instruction,
                    datasource_references=datasource_references,
                    options=geminidataanalytics.ConversationOptions(
                        analysis=geminidataanalytics.AnalysisOptions(
                            python=geminidataanalytics.AnalysisOptions.Python(
                                enabled=True
                            )
                        )
                    ),
                )

                data_agent = geminidataanalytics.DataAgent(
                    data_analytics_agent=geminidataanalytics.DataAnalyticsAgent(
                        published_context=published_context
                    ),
                    name=data_agent_client.data_agent_path(
                        billing_project, location, data_agent_id
                    ),
                    description=new_description,
                )

                update_mask = field_mask_pb2.FieldMask(
                    paths=["description", "data_analytics_agent.published_context"]
                )

                request = geminidataanalytics.UpdateDataAgentRequest(
                    data_agent=data_agent,
                    update_mask=update_mask,
                )

                data_agent_client.update_data_agent(request=request)
                st.success("✅ Data Agent Updated")
            except Exception as e:
                st.error(f"❌ Error updating Data Agent: {e}")
