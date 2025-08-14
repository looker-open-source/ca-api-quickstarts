# === FILE: app.py ===

import asyncio
import time
import os
import streamlit as st
from dotenv import load_dotenv
from auth import getAuthUrl, getCreds
from google.cloud import geminidataanalytics
from google.api_core import exceptions as google_exceptions

load_dotenv(override=True)

PROJECT_ID = os.getenv("PROJECT_ID")

def _init():
    if "creds" not in st.session_state:
        st.write("Please login")
        # TODO: investigate if we need asyncio
        auth_url = asyncio.run(getAuthUrl())
        if auth_url:
            st.markdown(f"[Login with Google]({auth_url})")

        code = st.query_params.get("code")
        if code:
            creds = asyncio.run(getCreds(code))
            if creds:
                st.query_params.clear()
                st.session_state.creds = creds
                st.rerun()
            else:
                st.error("Failed to login and get creds")
    else:
        if st.sidebar.button("Logout"):
            st.session_state.clear()
            st.rerun()
        
        # Initialize state
        if "initialized" not in st.session_state:
            st.session_state.project_id = PROJECT_ID
            st.session_state.dataqna_project_id = "bigquery-public-data"
            st.session_state.dataset_id = "san_francisco"
            st.session_state.table_ids = ("street_trees",)
            st.session_state.system_instruction = "answer questions"
            # if "looker_host" not in st.session_state:
            #     st.session_state.looker_host = "www.demo.com"
            # if "looker_secret" not in st.session_state:
            #     st.session_state.looker_secret = "fillin"
            # if "looker_client_id" not in st.session_state:
            #     st.session_state.looker_client_id = "fillin"
            # if "looker_explore" not in st.session_state:
            #     st.session_state.looker_explore = "fillin"
            # if "looker_model" not in st.session_state:
            #     st.session_state.looker_model = "fillin"
            # if "data_source" not in st.session_state:
            #     st.session_state.data_source = "BigQuery"
            with st.spinner("Loading"):
                st.session_state.data_agent_client = geminidataanalytics.DataAgentServiceClient(credentials=st.session_state.creds)
                try:
                    req = geminidataanalytics.ListDataAgentsRequest(
                        parent=f"projects/{st.session_state.project_id}/locations/global"
                    )
                    agents = list(st.session_state.data_agent_client.list_data_agents(request=req))
                    if not agents:
                        st.session_state.agents = []
                    for ag in agents:
                        st.session_state.agents = agents
                except google_exceptions.GoogleAPICallError as e:
                    st.error(f"API error fetching agents: {e}")
                except Exception as e:
                    st.error(f"Unexpected error: {e}")
            st.session_state.initialized = True

        pg = st.navigation([
                        st.Page("pages/agents.py",
                                title="Agents", icon="⚙️"),
                        st.Page("pages/chat.py",
                                title="Chat",
                                icon="🤖")])
        pg.run()

def main():
    st.set_page_config(
        page_title="CA API App",
        page_icon="🗣️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _init()

main()
