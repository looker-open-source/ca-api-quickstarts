import os
import getpass
from datetime import datetime, timezone

import google.auth
import streamlit as st
from dotenv import load_dotenv
from google.api_core import exceptions as google_exceptions
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import geminidataanalytics
from google.protobuf.field_mask_pb2 import FieldMask
from streamlit_extras.add_vertical_space import add_vertical_space
from error_handling import handle_errors


def get_adc_credentials(scopes=None):
    creds, project = google.auth.default(scopes=scopes)
    if not creds.valid:
        creds.refresh(GoogleAuthRequest())
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or project
    return creds, project


@handle_errors
def agents_main():
    st.set_page_config(page_title="Agents", page_icon="🤖", layout="wide")
    st.markdown(
        "<style>.block-container { padding-top: 0rem; }</style>",
        unsafe_allow_html=True,
    )

    load_dotenv()

    SCOPES = [
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/bigquery",
    ]
    creds, project_id = get_adc_credentials(SCOPES)
    st.session_state["adc_credentials"] = creds
    st.session_state["gcp_project_id"] = project_id

    col1, col2 = st.columns([5, 1])
    with col1:
        add_vertical_space(5)
        st.header("Agent Management")
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
                st.divider()
                st.write("**Authentication**")
                st.code("Application Default Credentials (ADC)", language="text")

    data_agent_client = geminidataanalytics.DataAgentServiceClient(credentials=creds)

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

    st.subheader("List and Show Agent Details")

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

    with st.form("filter_agents_form", clear_on_submit=False):
        f_col1, f_col2, f_col3 = st.columns([2, 2, 2])
        with f_col1:
            search_text = st.text_input(
                "Search (name/ID/description contains)",
                key="agents_search_text",
                placeholder="e.g., sales, agent_2025…",
            ).strip()
            only_with_desc = st.checkbox("Only show agents with description", value=False)
        with f_col2:
            created_from = st.date_input("Created from", value=None, key="agents_created_from")
            created_to = st.date_input("Created to", value=None, key="agents_created_to")
        with f_col3:
            sort_field = st.selectbox("Sort by", ["created", "updated"], index=0, key="agents_sort_field")
            sort_dir = st.selectbox("Direction", ["desc", "asc"], index=0, key="agents_sort_dir")
            max_items = st.number_input("Max results", 10, 1000, 10, key="agents_max_items")

        submitted = st.form_submit_button("Fetch Agents")

    if submitted:
        with st.spinner("Fetching agents..."):
            try:
                req = geminidataanalytics.ListDataAgentsRequest(
                    parent=f"projects/{billing_project}/locations/global"
                )
                agents = list(data_agent_client.list_data_agents(request=req))
            except google_exceptions.GoogleAPICallError as e:
                st.error(f"API error fetching agents: {e}")
                agents = []
            except Exception as e:
                st.error(f"Unexpected error: {e}")
                agents = []

        original_count = len(agents)

        q = search_text.lower()
        def matches_text(ag) -> bool:
            if not q:
                return True
            display = (ag.display_name or "").lower()
            name = (ag.name or "").lower()
            desc = (ag.description or "").lower()
            return (q in display) or (q in name) or (q in desc)

        def matches_desc(ag) -> bool:
            return (not only_with_desc) or bool(getattr(ag, "description", None))

        def within_created_range(ag) -> bool:
            dt = ts_to_dt(getattr(ag, "create_time", None))
            if dt is None:
                return False if (created_from or created_to) else True
            if created_from:
                if dt < datetime.combine(created_from, datetime.min.time(), tzinfo=timezone.utc):
                    return False
            if created_to:
                if dt > datetime.combine(created_to, datetime.max.time(), tzinfo=timezone.utc):
                    return False
            return True

        filtered = [ag for ag in agents if matches_text(ag) and matches_desc(ag) and within_created_range(ag)]

        def sort_key(ag):
            if sort_field == "updated":
                dt = ts_to_dt(getattr(ag, "update_time", None))
            else:
                dt = ts_to_dt(getattr(ag, "create_time", None))
            return dt or datetime.min.replace(tzinfo=timezone.utc)

        reverse = (sort_dir == "desc")
        filtered.sort(key=sort_key, reverse=reverse)

        filtered = filtered[: int(max_items)]

        st.caption(f"Showing {len(filtered)} of {original_count} agents (after filters).")

        if not filtered:
            st.info("No agents match the selected filters.")
        else:
            for ag in filtered:
                disp = ag.display_name or ag.name.split("/")[-1]
                created = ts_to_dt(getattr(ag, "create_time", None))
                updated = ts_to_dt(getattr(ag, "update_time", None))
                created_s = created.isoformat() if created else "—"
                updated_s = updated.isoformat() if updated else "—"

                with st.expander(disp):
                    st.write(f"**Resource:** `{ag.name}`")
                    if ag.description:
                        st.write(f"**Description:** {ag.description}")
                    st.write(f"**Created:** {created_s}")
                    st.write(f"**Updated:** {updated_s}")

    st.divider()

    st.subheader("Update a Data Agent")
    agent_id_to_update = st.text_input(
        "Agent ID to update",
        key="update_agent_id",
        help="Enter the final part of the agent resource name (e.g., 'agent_20250729120000')",
    )
    new_description = st.text_area("New description", key="update_desc")
    if st.button("Update Agent Description"):
        if not agent_id_to_update or not new_description:
            st.warning("Please provide both an Agent ID and a new description.")
        else:
            try:
                path = data_agent_client.data_agent_path(
                    billing_project, "global", agent_id_to_update
                )
                agent = geminidataanalytics.DataAgent(
                    name=path, description=new_description
                )
                mask = FieldMask(paths=["description"])
                data_agent_client.update_data_agent(agent=agent, update_mask=mask)
                st.success(f"Agent '{agent_id_to_update}' updated successfully!")
            except google_exceptions.GoogleAPICallError as e:
                st.error(f"API error updating agent: {e}")
            except Exception as e:
                st.error(f"Unexpected error: {e}")


agents_main()