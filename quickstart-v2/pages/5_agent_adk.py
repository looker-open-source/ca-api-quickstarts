# quickstart-v2/pages/4_agent_adk.py
import os
import asyncio
import getpass
from typing import List, Tuple
import logging
import warnings
import re
import requests
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import google.auth
import streamlit as st
from dotenv import load_dotenv
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.api_core import exceptions as google_exceptions
from google.cloud import geminidataanalytics
from streamlit_extras.add_vertical_space import add_vertical_space

from error_handling import handle_errors

MODEL = "gemini-2.5-pro"
MODEL_AVATAR_URL = "https://www.gstatic.com/images/branding/productlogos/gemini_2025/v1/web-24dp/logo_gemini_2025_color_1x_web_24dp.png"


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
    st.set_page_config(page_title="Google Agent Development Kit Chat", page_icon="🧠", layout="wide")
    st.markdown("<style>.block-container { padding-top: 0rem; }</style>", unsafe_allow_html=True)
    load_dotenv()
    logging.getLogger('asyncio').setLevel(logging.CRITICAL)
    warnings.filterwarnings("ignore", message=".*coroutine '.*' was never awaited.*")

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
        st.header("Google Agent Develoment Kit Chat")
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
        "GCP Billing Project ID",
        get_default_project_id(),
        key="billing_project_adk"
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

    adk_instruction = (
        "You are a specialized assistant with multiple tools. Your goal is to be as helpful as possible.\n"
        "- For questions about connected data sources (airports), first try the `call_gemini_data_analytics_tool`.\n"
        "- For real-time weather, first try the `get_weather` tool.\n"
        "- **Crucially, if a tool does not provide a satisfactory answer or returns '__NO_RESULT__', you must then try to answer the question using your general knowledge.**\n"
        "- For all other questions, use your general knowledge directly.\n"
        "Maintain conversation context and only use tools when appropriate."
    )

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
        st.info("Install ADK with: pip install google-adk")

    def get_weather_description(wmo_code: int) -> str:
        """Converts WMO weather code to a human-readable description."""
        wmo_codes = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
            55: "Dense drizzle", 56: "Light freezing drizzle", 57: "Dense freezing drizzle",
            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
            66: "Light freezing rain", 67: "Heavy freezing rain", 71: "Slight snow fall",
            73: "Moderate snow fall", 75: "Heavy snow fall", 77: "Snow grains",
            80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
            85: "Slight snow showers", 86: "Heavy snow showers", 95: "Thunderstorm",
            96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
        }
        return wmo_codes.get(wmo_code, "Unknown weather condition")

    def get_weather(query: str, unit: str = "fahrenheit") -> str:
        """
        Fetches the real-time weather for a city by parsing the city name from
        the query and calling the Open-Meteo API.
        """
        st.info(f"Tool Invocation: get_weather was selected for query: '{query}'")
        match = re.search(r"\b(?:in|for|at)\s+([\w\s,]+)", query, re.IGNORECASE)
        if not match:
            return "I couldn't figure out which city you're asking about. Please phrase your query like 'weather in New York'."
        city = match.group(1).strip().strip(',')
        try:
            geocoding_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
            geo_response = requests.get(geocoding_url, timeout=10)
            geo_response.raise_for_status()
            geo_data = geo_response.json()

            if not geo_data.get("results"):
                return f"I couldn't find the location for '{city}'. Please check the spelling."

            location = geo_data["results"][0]
            latitude = location["latitude"]
            longitude = location["longitude"]
            name = location.get("name", city)
            admin1 = location.get("admin1", "")
            country = location.get("country", "")
            location_display = f"{name}, {admin1}, {country}".strip(", ").replace(" ,", ",")

            weather_url = (f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}"
                           f"&current_weather=true&temperature_unit={unit}&timezone=auto")
            weather_response = requests.get(weather_url, timeout=10)
            weather_response.raise_for_status()
            weather_data = weather_response.json()

            current_weather = weather_data["current_weather"]
            temp, wmo_code = current_weather["temperature"], current_weather["weathercode"]
            temp_unit = "°F" if unit == "fahrenheit" else "°C"
            weather_desc = get_weather_description(wmo_code)
            local_datetime = datetime.fromisoformat(current_weather["time"]).astimezone(ZoneInfo(weather_data["timezone"]))
            formatted_time = local_datetime.strftime("%A, %b %d, %Y @ %I:%M %p")

            return (f"As of **{formatted_time}** local time, the current weather in "
                    f"**{location_display}** is **{temp}{temp_unit}** with **{weather_desc}**.")
        except requests.exceptions.RequestException as e:
            return f"I couldn't connect to the weather service. Error: {e}"
        except (KeyError, IndexError, ZoneInfoNotFoundError):
            return "There was an issue parsing the weather or time data from the API."

    def call_gemini_data_analytics_tool(user_message: str) -> str:
        """Queries Gemini Data Analytics and returns its output directly to the agent."""
        if not agent_choice:
            return "Error: No Data Agent was selected in the sidebar."
        st.info(f"Tool Invocation: call_gemini_data_analytics_tool was selected for query: '{user_message}'")
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
                elif getattr(resp, "system_message", None) and getattr(resp.system_message, "text", None):
                    t = resp.system_message.text
                    if hasattr(t, "parts"):
                        chunks.append("".join(str(s) for s in t.parts))
        except Exception as e:
            return f"(Tool error: {e})"

        result = "\n".join(c for c in chunks if c).strip()

        failure_phrases = [
            "sorry",
            "i cannot answer",
            "i can't answer",
            "do not have information",
            "unable to answer",
            "does not contain information",
        ]
        if not result or any(phrase in result.lower() for phrase in failure_phrases):
            return "__NO_RESULT__"

        return result

    def make_adk_tool(func):
        """Helper to create a FunctionTool if available, otherwise return the raw function."""
        if FunctionTool is None:
            return func
        try:
            return FunctionTool(func=func)
        except TypeError:
            return func

    def process_adk_events(events) -> Tuple[str, List[str]]:
        """
        Processes events from an ADK runner, extracting the final text response
        and a list of any tools that were successfully used.
        """
        buf = []
        tools_called = set()
        tools_failed = set()

        for ev in events:
            if content := getattr(ev, "content", None):
                if parts := getattr(content, "parts", None):
                    for p in parts:
                        # A part can be a function call, indicating a tool was invoked.
                        if fc := getattr(p, "function_call", None):
                            tools_called.add(fc.name)
                        # A part can also be the response from that function call.
                        if fr := getattr(p, "function_response", None):
                            # The response content is itself a list of parts.
                            response_parts = getattr(fr, "content", [])
                            for resp_part in response_parts:
                                # Check if the tool returned our specific failure signal.
                                if getattr(resp_part, "text", "") == "__NO_RESULT__":
                                    tools_failed.add(fr.name)
                        # A part can also be simple text from the LLM.
                        if text := getattr(p, "text", None):
                            buf.append(text)

            # Stop processing on the final response event to be efficient.
            if bool(getattr(ev, "final_response", False)):
                break

        final_answer = "".join(buf).strip()
        # The successfully used tools are those that were called but did not fail.
        successful_tools = list(tools_called - tools_failed)
        return final_answer, successful_tools

    def build_or_refresh_runner(instruction: str, tools: list):
        """Builds or rebuilds the ADK runner with the given instruction and tools."""
        adk_agent = Agent(
            model=MODEL,
            name="caapi_multi_tool_agent",
            instruction=instruction,
            tools=tools,
        )
        session_service = st.session_state.adk_session_service
        st.session_state["adk_runner"] = Runner(
            app_name=APP_NAME,
            session_service=session_service,
            agent=adk_agent,
        )
        ensure_adk_session(session_service, APP_NAME, USER_ID, st.session_state.get("adk_session_id", DEFAULT_SESSION_ID))

    APP_NAME = "caapi-streamlit-adk"
    DEFAULT_SESSION_ID = "session-adk"
    USER_ID = getpass.getuser() or "local-user"

    if adk_available and "adk_session_service" not in st.session_state:
        st.session_state.adk_session_service = InMemorySessionService()

    if adk_available:
        all_tools = [make_adk_tool(call_gemini_data_analytics_tool), make_adk_tool(get_weather)]
        runner = st.session_state.get("adk_runner")
        if not runner or getattr(runner.agent, "instruction", "") != adk_instruction:
            build_or_refresh_runner(adk_instruction, all_tools)

    st.divider()
    st.subheader("Chat")

    if "adk_messages" not in st.session_state:
        st.session_state["adk_messages"] = []

    for msg in st.session_state["adk_messages"]:
        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar=MODEL_AVATAR_URL):
                st.markdown(msg["content"])
                provenance = msg.get("provenance")
                if provenance is not None:
                    with st.expander("✨ Answer Provenance", expanded=False):
                        if provenance:
                            st.write("The following tools were used to generate this answer:")
                            for tool_name in provenance:
                                st.code(f"🛠️ {tool_name}", language=None)
                        else:
                            st.write("This answer was generated directly by the language model.")
                            st.code(f"🧠 {MODEL}", language=None)
        else:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])


    user_input = st.chat_input("Ask the agent…")

    if user_input:
        st.session_state["adk_messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant", avatar=MODEL_AVATAR_URL):
            with st.spinner("Thinking with Gemini…"):
                try:
                    runner: "Runner" = st.session_state["adk_runner"]
                    session_id = st.session_state.get("adk_session_id", DEFAULT_SESSION_ID)
                    content = genai_types.Content(role="user", parts=[genai_types.Part(text=user_input)])

                    try:
                        events = runner.run(user_id=USER_ID, session_id=session_id, new_message=content)
                    except ValueError as e:
                        if "Session not found" in str(e):
                            ensure_adk_session(runner.session_service, runner.app_name, USER_ID, session_id)
                            events = runner.run(user_id=USER_ID, session_id=session_id, new_message=content)
                        else:
                            raise

                    answer, tools_used = process_adk_events(events)
                    answer = answer or "(The agent returned no text)"

                    st.markdown(answer)

                    with st.expander("✨ Answer Provenance", expanded=True):
                        if tools_used:
                            st.write("The following tools were used to generate this answer:")
                            for tool_name in tools_used:
                                st.code(f"🛠️ {tool_name}", language=None)
                        else:
                            st.write("This answer was generated directly by the language model.")
                            st.code(f"🧠 {MODEL}", language=None)

                    st.session_state["adk_messages"].append(
                        {"role": "assistant", "content": answer, "provenance": tools_used}
                    )

                except Exception as e:
                    st.error(f"Agent error: {e}")

    if agent_choice:
        st.caption(f"Using Data Agent: {name_to_disp.get(agent_choice, agent_choice)}")

agent_chat_adk_main()