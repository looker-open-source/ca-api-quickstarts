#quickstart-v2/pages/4_agent_adk.py

import os
import asyncio
import getpass
from typing import List
import logging # Added for warning suppression
import warnings # Added for warning suppression

import google.auth
import streamlit as st
from dotenv import load_dotenv
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.api_core import exceptions as google_exceptions
from google.cloud import geminidataanalytics
from streamlit_extras.add_vertical_space import add_vertical_space
MODEL = "gemini-2.5-pro"

from error_handling import handle_errors

@handle_errors
def get_adc_credentials(scopes=None):
    creds, project = google.auth.default(scopes=scopes)
    if not creds.valid:
        creds.refresh(GoogleAuthRequest())
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or project
    return creds, project


@handle_errors
@st.cache_data(show_spinner=False, ttl=60)
def list_data_agents(_creds, billing_project: str):
    """Cached list call; underscore prevents hashing creds."""
    client = geminidataanalytics.DataAgentServiceClient(credentials=_creds)
    req = geminidataanalytics.ListDataAgentsRequest(
        parent=f"projects/{billing_project}/locations/global"
    )
    return list(client.list_data_agents(request=req))

@handle_errors
def ensure_adk_session(session_service, app_name: str, user_id: str, session_id: str):
    """
    Create the ADK session if it doesn't already exist.
    Handles async/sync implementations across ADK versions.
    """
    try:
        create_fn = session_service.create_session
        if asyncio.iscoroutinefunction(create_fn):
            asyncio.run(create_fn(app_name=app_name, user_id=user_id, session_id=session_id))
        else:
            create_fn(app_name=app_name, user_id=user_id, session_id=session_id)
    except Exception:
        pass

@handle_errors
def agent_chat_adk_main():
    st.set_page_config(page_title="Agent Chat (ADK)", page_icon="🧠", layout="wide")
    st.markdown("<style>.block-container { padding-top: 0rem; }</style>", unsafe_allow_html=True)
    load_dotenv()

    # --- CHANGE: Added warning suppression ---
    logging.getLogger('asyncio').setLevel(logging.CRITICAL)
    warnings.filterwarnings("ignore", message=".*coroutine '.*' was never awaited.*")
    # ----------------------------------------

    SCOPES = [
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/bigquery",
    ]
    
    creds, project_id = get_adc_credentials(SCOPES)
    st.session_state["adc_credentials"] = creds
    st.session_state["gcp_project_id"] = project_id

    vertex_region = "us-central1" 

    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id 
    os.environ["GOOGLE_CLOUD_LOCATION"] = vertex_region


    col1, col2 = st.columns([5, 1])
    with col1:
        add_vertical_space(5)
        st.header("Agent Chat (ADK)")
        st.caption("Use an Agent Development Kit (ADK) agent that calls Gemini Data Analytics as a tool.")
    with col2:
        os_user = getpass.getuser()
        if os_user:
            with st.popover(
                f"👤 {os_user}",
                use_container_width=True,
                help="Authenticated via Application Default Credentials",
            ):
                st.markdown(f"**{os_user}**")
                sa_email = getattr(creds, "service_account_email", None)
                if sa_email:
                    st.caption(sa_email)
                st.caption(f"Project: {project_id}")

    @st.cache_data
    def get_default_project_id():
        try:
            _, pid = google.auth.default()
            return os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or pid
        except Exception:
            return None

    st.sidebar.header("Settings")
    billing_project = st.sidebar.text_input(
        "GCP Billing Project ID", get_default_project_id(), key="billing_project_adk"
    )
    if not billing_project:
        st.sidebar.error("Please enter your GCP Billing Project ID")
        st.stop()

    st.sidebar.subheader("Pick a Data Agent")
    try:
        agents = list_data_agents(creds, billing_project)
    except google_exceptions.GoogleAPICallError as e:
        st.sidebar.error(f"API error listing agents: {e}")
        agents = []
    except Exception as e:
        st.sidebar.error(f"Unexpected error listing agents: {e}")
        agents = []

    name_to_disp = {a.name: (a.display_name or a.name.split("/")[-1]) for a in agents}
    agent_choice = st.sidebar.selectbox(
        "Data Agent",
        options=list(name_to_disp.keys()),
        format_func=lambda n: name_to_disp.get(n, n),
        key="adk_selected_agent_name",
    )

    st.sidebar.subheader("ADK Agent Instruction")
    # --- CHANGE: Updated the default agent instruction value ---
    adk_instruction = st.sidebar.text_area(
        "System instruction for the ADK agent",
        value=(
            "You are a specialized assistant with two distinct functions:\n\n"
            "1. **For any questions that can be answered by the connected data source, "
            "you MUST use the `call_gemini_data_analytics_tool`.** This is your "
            "primary method for data retrieval.\n\n"
            "2. **For ALL OTHER questions (e.g., weather, geography, general knowledge, providing "
            "information not found by the tool), you MUST use your own internal knowledge.** "
            "If the tool fails or returns no information, rely on your general "
            "knowledge to answer the user's question. Do NOT attempt to use the data "
            "tool for these general questions.\n\n"
            "Always maintain the context of the conversation. If a follow-up question "
            "refers to a subject from a previous data query, use that contextual "
            "information to answer the new, general knowledge question."
        ),
        height=280, # Increased height to fit the new text
        key="adk_agent_instruction",
    )
    # -------------------------------------------------------------

    try:
        from google.adk.agents import Agent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types as genai_types
        try:
            from google.adk.tools import FunctionTool
        except Exception:
            FunctionTool = None
        adk_available = True
    except Exception as e:
        adk_available = False
        st.exception(e)
        st.info("Install ADK with: `pip install google-adk`")


    def call_gemini_data_analytics_tool(user_message: str) -> str:
        """
        Queries Gemini Data Analytics and returns its output directly to the agent.
        """
        if not agent_choice:
            return "Error: No Data Agent was selected in the sidebar."

        client = geminidataanalytics.DataChatServiceClient(credentials=creds)

        msg = geminidataanalytics.Message(user_message={"text": user_message})
        da_ctx = geminidataanalytics.DataAgentContext(data_agent=agent_choice)

        req = geminidataanalytics.ChatRequest(
            parent=f"projects/{billing_project}/locations/global",
            messages=[msg],
            data_agent_context=da_ctx,
        )

        chunks: List[str] = []
        try:
            for resp in client.chat(request=req):
                if getattr(resp, "model_message", None) and getattr(resp.model_message, "text", None):
                    chunks.append(str(resp.model_message.text))
                elif getattr(resp, "agent_message", None) and getattr(resp.agent_message, "text", None):
                    chunks.append(str(resp.agent_message.text))
                elif getattr(resp, "system_message", None) and getattr(resp.system_message, "text", None):
                    t = resp.system_message.text
                    if hasattr(t, "parts"):
                        chunks.append("".join(str(s) for s in t.parts))
        except Exception as e:
            return f"(Tool error: {e})"

        result = "\n".join(c for c in chunks if c).strip()

        if not result:
            return "The data tool was called but returned no information."
        
        return result

    def make_query_tool():
        if FunctionTool is None:
            return call_gemini_data_analytics_tool
        try:
            return FunctionTool(func=call_gemini_data_analytics_tool)
        except TypeError:
            return call_gemini_data_analytics_tool

    def _collect_text_from_events(events) -> str:
        buf = []
        final_seen = False
        for ev in events:
            is_final = False
            if hasattr(ev, "is_final_response") and callable(ev.is_final_response):
                is_final = ev.is_final_response()
            elif hasattr(ev, "final_response"):
                is_final = bool(getattr(ev, "final_response"))

            content = getattr(ev, "content", None)
            parts = getattr(content, "parts", None) if content is not None else None
            if parts:
                for p in parts:
                    if getattr(p, "text", None):
                        buf.append(p.text)
                    elif isinstance(p, dict) and p.get("text"):
                        buf.append(p["text"])
            if is_final:
                final_seen = True
                break
        text = "".join(buf).strip()
        return text if text else ("" if final_seen else "")

    # ---- Build or refresh the ADK runner & CREATE THE SESSION ----
    APP_NAME = "caapi-streamlit-adk"
    DEFAULT_SESSION_ID = "session-adk"
    USER_ID = getpass.getuser() or "local-user"

    if adk_available and "adk_session_service" not in st.session_state:
        st.session_state.adk_session_service = InMemorySessionService()

    if adk_available and "adk_runner" not in st.session_state:
        query_tool = make_query_tool()
        adk_agent = Agent(
            model=MODEL,
            name="caapi_data_analysis_agent",
            description="Answers questions about structured data using Gemini Data Analytics as a tool.",
            instruction=adk_instruction,
            tools=[query_tool],
        )
        session_service = st.session_state.adk_session_service
        st.session_state["adk_runner"] = Runner(
            app_name=APP_NAME,
            session_service=session_service,
            agent=adk_agent,
        )
        st.session_state["adk_session_id"] = DEFAULT_SESSION_ID
        ensure_adk_session(session_service, APP_NAME, USER_ID, DEFAULT_SESSION_ID)

    if adk_available and "adk_runner" in st.session_state:
        runner: "Runner" = st.session_state["adk_runner"]
        if getattr(runner.agent, "instruction", "") != adk_instruction:
            query_tool = make_query_tool()
            adk_agent = Agent(
                model=MODEL,
                name="caapi_data_analysis_agent",
                description="Answers questions about structured data using Gemini Data Analytics as a tool.",
                instruction=adk_instruction,
                tools=[query_tool],
            )
            session_service = st.session_state.adk_session_service
            st.session_state["adk_runner"] = Runner(
                app_name=APP_NAME,
                session_service=session_service,
                agent=adk_agent,
            )
            ensure_adk_session(session_service, APP_NAME, USER_ID, st.session_state.get("adk_session_id", DEFAULT_SESSION_ID))

    # ---- Chat UI ----
    st.divider()
    st.subheader("Chat")

    if "adk_messages" not in st.session_state:
        st.session_state["adk_messages"] = []

    for msg in st.session_state["adk_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Ask the agent…")
    if user_input:
        st.session_state["adk_messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking with ADK…"):
                if not adk_available:
                    st.error("ADK not installed. Install `google-adk` to use this page.")
                elif not agent_choice:
                    st.error("Please select a Data Agent in the sidebar.")
                else:
                    try:
                        runner: "Runner" = st.session_state["adk_runner"]
                        session_id = st.session_state.get("adk_session_id", DEFAULT_SESSION_ID)

                        content = genai_types.Content(
                            role="user", parts=[genai_types.Part(text=user_input)]
                        )

                        try:
                            events = runner.run(user_id=USER_ID, session_id=session_id, new_message=content)
                        except ValueError as e:
                            if "Session not found" in str(e):
                                ensure_adk_session(runner.session_service, runner.app_name, USER_ID, session_id)
                                events = runner.run(user_id=USER_ID, session_id=session_id, new_message=content)
                            else:
                                raise

                        answer = _collect_text_from_events(events) or "(no text)"
                        st.markdown(answer)
                        st.session_state["adk_messages"].append({"role": "assistant", "content": answer})
                    except Exception as e:
                        st.error(f"ADK run error: {e}")

    if agent_choice:
        st.caption(f"Using Data Agent: `{name_to_disp.get(agent_choice, agent_choice)}`")


agent_chat_adk_main()