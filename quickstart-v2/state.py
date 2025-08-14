import streamlit as st
from google.cloud import geminidataanalytics
from google.api_core import exceptions as google_exceptions

def refresh_agents_state(): 
    try:
        req = geminidataanalytics.ListDataAgentsRequest(
            parent=f"projects/{st.session_state.project_id}/locations/global"
        )
        agents = list(st.session_state.data_agent_client.list_data_agents(request=req))
        if not agents:
            st.session_state.agents = []
        for ag in agents:
            st.session_state.agents = agents
        st.rerun()
    except google_exceptions.GoogleAPICallError as e:
        st.error(f"API error fetching agents: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")