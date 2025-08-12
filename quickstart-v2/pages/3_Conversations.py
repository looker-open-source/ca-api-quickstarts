import os
import getpass
from datetime import datetime, timezone

import google.auth
import streamlit as st
from dotenv import load_dotenv
from google.api_core import exceptions as google_exceptions
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import geminidataanalytics
from streamlit_extras.add_vertical_space import add_vertical_space
from error_handling import handle_errors


def get_adc_credentials(scopes=None):
    creds, project = google.auth.default(scopes=scopes)
    if not creds.valid:
        creds.refresh(GoogleAuthRequest())
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or project
    return creds, project


def ts_to_dt(ts):
    try:
        return ts.ToDatetime().astimezone(timezone.utc)
    except Exception:
        try:
            s = str(ts)
            if s.endswith("Z"):
                s = s.replace("Z", "+00:00")
            return datetime.fromisoformat(s).astimezone(timezone.utc)
        except Exception:
            return None


@handle_errors
def conversations_main():
    st.set_page_config(page_title="Conversations", page_icon="📜", layout="wide")
    st.markdown("<style>.block-container { padding-top: 0rem; }</style>", unsafe_allow_html=True)
    load_dotenv()

    SCOPES = ["https://www.googleapis.com/auth/cloud-platform", "https://www.googleapis.com/auth/bigquery"]
    creds, project_id = get_adc_credentials(SCOPES)
    st.session_state["adc_credentials"] = creds
    st.session_state["gcp_project_id"] = project_id

    client_agents = geminidataanalytics.DataAgentServiceClient(credentials=creds)
    client_chat = geminidataanalytics.DataChatServiceClient(credentials=creds)

    col1, col2 = st.columns([5, 1])
    with col1:
        add_vertical_space(5)
        st.header("Conversation History")
    with col2:
        os_user = getpass.getuser()
        if os_user:
            with st.popover(f"👤 {os_user}", use_container_width=True,
                            help="Authenticated via Application Default Credentials"):
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
        "GCP Billing Project ID", get_default_project_id(), key="billing_project"
    )
    if not billing_project:
        st.sidebar.error("Please enter your GCP Billing Project ID")
        st.stop()

    SESSION_AGENTS_MAP = "agents_map"
    SESSION_CONVERSATIONS = "conversations"
    if SESSION_AGENTS_MAP not in st.session_state:
        st.session_state[SESSION_AGENTS_MAP] = {}
    if SESSION_CONVERSATIONS not in st.session_state:
        st.session_state[SESSION_CONVERSATIONS] = []

    st.subheader("List & Filter Conversations")

    with st.form("filter_conversations_form", clear_on_submit=False):
        f1, f2, f3 = st.columns([2, 2, 2])
        with f1:
            search_text = st.text_input(
                "Search messages (contains)",
                key="conv_search_text",
                placeholder="e.g., airport elevation, revenue, …",
            ).strip()
            include_assistant = st.checkbox("Include assistant messages", value=True, key="conv_include_assistant")
        with f2:
            date_from = st.date_input("Last used from", value=None, key="conv_from")
            date_to = st.date_input("Last used to", value=None, key="conv_to")
        with f3:
            sort_field = st.selectbox("Sort by", ["last_used", "created"], index=0, key="conv_sort_field")
            sort_dir = st.selectbox("Direction", ["desc", "asc"], index=0, key="conv_sort_dir")
            max_items = st.number_input("Max results", 10, 1000, 200, step=10, key="conv_max_items")

        submitted = st.form_submit_button("Load Conversations")

    if submitted:
        with st.spinner("Loading agents & conversations…"):
            try:
                agents = list(
                    client_agents.list_data_agents(parent=f"projects/{billing_project}/locations/global")
                )
                st.session_state[SESSION_AGENTS_MAP] = {a.name: a for a in agents}
            except google_exceptions.GoogleAPICallError as e:
                st.error(f"API error loading agents: {e}")
                st.session_state[SESSION_AGENTS_MAP] = {}
            try:
                convos = list(
                    client_chat.list_conversations(parent=f"projects/{billing_project}/locations/global")
                )
                st.session_state[SESSION_CONVERSATIONS] = convos
                if not convos:
                    st.info("No conversations found.")
            except google_exceptions.GoogleAPICallError as e:
                st.error(f"API error loading conversations: {e}")
                st.session_state[SESSION_CONVERSATIONS] = []
            except Exception as e:
                st.error(f"Unexpected error: {e}")
                st.session_state[SESSION_CONVERSATIONS] = []

    convs = st.session_state[SESSION_CONVERSATIONS]
    agents_map = st.session_state[SESSION_AGENTS_MAP]

    agent_choices = sorted(agents_map.keys())
    picked_agents = st.multiselect(
        "Filter by Agent(s)",
        options=agent_choices,
        format_func=lambda k: agents_map[k].display_name or k.split("/")[-1],
        key="conv_agent_filter",
    ) if agent_choices else []

    @st.cache_data(show_spinner=False)
    def load_messages_for_conversation(conv_name: str):
        return list(client_chat.list_messages(parent=conv_name))

    def matches_agent(c):
        if not picked_agents:
            return True
        try:
            conv_agents = set(getattr(c, "agents", []) or [])
        except Exception:
            conv_agents = set()
        return bool(conv_agents & set(picked_agents))

    def matches_date(c):
        if not (date_from or date_to):
            return True
        dt = ts_to_dt(getattr(c, "last_used_time", None))
        if dt is None:
            return False
        if date_from:
            if dt < datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc):
                return False
        if date_to:
            if dt > datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc):
                return False
        return True

    prelim = [c for c in convs if matches_agent(c) and matches_date(c)]

    q = search_text.lower()
    if q:
        with st.spinner("Searching messages…"):
            def message_matches(conv_name: str) -> bool:
                try:
                    msgs = load_messages_for_conversation(conv_name)
                except Exception:
                    return False
                for m in msgs:
                    utxt = getattr(getattr(m, "user_message", None), "text", None)
                    if isinstance(utxt, str) and q in utxt.lower():
                        return True
                    if include_assistant:
                        sm = getattr(m, "system_message", None)
                        t = getattr(sm, "text", None)
                        parts = getattr(t, "parts", None) if t else None
                        if parts:
                            for p in parts:
                                s = str(p)
                                if q in s.lower():
                                    return True
                return False

            filtered = [c for c in prelim if message_matches(c.name)]
    else:
        filtered = prelim

    def sort_key(c):
        if st.session_state["conv_sort_field"] == "created":
            dt = ts_to_dt(getattr(c, "create_time", None))
        else:
            dt = ts_to_dt(getattr(c, "last_used_time", None))
        return dt or datetime.min.replace(tzinfo=timezone.utc)

    reverse = (st.session_state["conv_sort_dir"] == "desc")
    filtered.sort(key=sort_key, reverse=reverse)
    filtered = filtered[: int(st.session_state["conv_max_items"])]

    st.caption(f"Showing {len(filtered)} of {len(convs)} conversations (after filters).")

    for conv in filtered:
        cid = conv.name.split("/")[-1]
        last_used_dt = ts_to_dt(getattr(conv, "last_used_time", None))
        created_dt = ts_to_dt(getattr(conv, "create_time", None))
        last_used_s = last_used_dt.isoformat() if last_used_dt else "—"
        created_s = created_dt.isoformat() if created_dt else "—"

        agent_badges = []
        for a in getattr(conv, "agents", []):
            disp = agents_map.get(a).display_name if a in agents_map else a.split("/")[-1]
            agent_badges.append(f"`{disp}`")
        badges = "  ".join(agent_badges) if agent_badges else "—"

        with st.expander(f"Conversation: `{cid}`  •  Last Used: {last_used_s}"):
            st.write(f"**Resource:** `{conv.name}`")
            st.write(f"**Created:** {created_s}")
            st.write(f"**Agents:** {badges}")

            show_raw = st.checkbox("Show raw message JSON (for debugging)", value=False, key=f"raw_{cid}")

            def _parts_to_text(parts):
                if parts is None:
                    return ""
                if isinstance(parts, (list, tuple)):
                    return "".join(str(p) for p in parts)
                return str(parts)

            def _msg_to_dict(m):
                to_dict = getattr(m, "to_dict", None)
                if callable(to_dict):
                    return to_dict()
                try:
                    from google.protobuf.json_format import MessageToDict
                    return MessageToDict(m, preserving_proto_field_name=True)
                except Exception:
                    return {"_repr": str(m)}

            def extract_display_text(m):
                um = getattr(m, "user_message", None)
                if um is not None:
                    utxt = getattr(um, "text", None)
                    return ("user", utxt if isinstance(utxt, str) else (str(utxt) if utxt else ""), {})

                am = getattr(m, "assistant_message", None)
                if am is not None:
                    txt = getattr(am, "text", None)
                    if txt is not None:
                        parts = getattr(txt, "parts", None)
                        if parts:
                            return ("assistant", _parts_to_text(parts), {})
                        if isinstance(txt, str):
                            return ("assistant", txt, {})

                    extras = {}
                    data = getattr(am, "data", None)
                    if data is not None:
                        gen_sql = getattr(data, "generated_sql", None)
                        if gen_sql:
                            extras["generated_sql"] = gen_sql
                        result = getattr(data, "result", None)
                        if result is not None:
                            rows = getattr(result, "data", None) or []
                            extras["rows"] = len(rows)
                    chart = getattr(am, "chart", None)
                    if chart is not None:
                        extras["chart"] = True

                    return ("assistant", "", extras)

                sm = getattr(m, "system_message", None)
                if sm is not None:
                    t = getattr(sm, "text", None)
                    parts = getattr(t, "parts", None) if t else None
                    if parts:
                        return ("assistant", _parts_to_text(parts), {})
                    if isinstance(t, str):
                        return ("assistant", t, {})

                return ("assistant", "", {})

            if st.button(f"View Messages for {cid}", key=f"view_{cid}"):
                with st.spinner(f"Fetching messages for {cid}…"):
                    try:
                        msgs = load_messages_for_conversation(conv.name)
                        for m in msgs:
                            role = "user" if getattr(m, "user_message", None) else "assistant"

                            with st.chat_message(role):
                                text_to_show = ""

                                if role == "user":
                                    text_to_show = getattr(getattr(m, "user_message", None), "text", "") or ""
                                else:
                                    am = getattr(m, "assistant_message", None)
                                    if am and getattr(am, "text", None):
                                        parts = getattr(am.text, "parts", None)
                                        if parts:
                                            text_to_show = "".join(parts)

                                    if not text_to_show:
                                        sm = getattr(m, "system_message", None)
                                        if sm and getattr(sm, "text", None):
                                            parts = getattr(sm.text, "parts", None)
                                            if parts:
                                                text_to_show = "".join(parts)

                                st.markdown(text_to_show if text_to_show else "(no text)")

                    except Exception as e:
                        st.error(f"Message load error: {e}")

conversations_main()