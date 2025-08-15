import os
import streamlit as st
from google.cloud import geminidataanalytics
from google.api_core import exceptions as google_exceptions
from dotenv import load_dotenv

load_dotenv(override=True)

PROJECT_ID = os.getenv("PROJECT_ID")
LOOKER_CLIENT_ID = os.getenv("LOOKER_CLIENT_ID")
LOOKER_CLIENT_SECRET = os.getenv("LOOKER_CLIENT_SECRET")

# Depends on session_state.creds being set
def init_state():
    st.session_state.project_id = PROJECT_ID
    st.session_state.agents = []
    st.session_state.convos = []
    st.session_state.convo_messages = []

    st.session_state.data_agent_client = geminidataanalytics.DataAgentServiceClient(credentials=st.session_state.creds)

    st.session_state.data_chat_client = geminidataanalytics.DataChatServiceClient(credentials=st.session_state.creds)

    fetch_agents_state(rerun=False)
    st.session_state.agent_index = 0 if len(st.session_state.agents) > 0 else -1

    fetch_convos_state(rerun=False)
    st.session_state.convo_index = 0 if len(st.session_state.convos) > 0 else -1

    fetch_messages_state(rerun=False)

    st.session_state.initialized = True
    st.rerun()

# fetch all agents
def fetch_agents_state(rerun=True): 
    client = st.session_state.data_agent_client 
    project_id = st.session_state.project_id

    try:
        request = geminidataanalytics.ListDataAgentsRequest(
            parent=f"projects/{project_id}/locations/global"
        )
        agents = list(client.list_data_agents(request=request))
        st.session_state.agents = agents if len(agents) > 0 else []
        if rerun:
            st.rerun()
    except google_exceptions.GoogleAPICallError as e:
        st.error(f"API error fetching agents: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")

# Limited to fetching 100 conversations from selected agent
def fetch_convos_state(rerun=True):
    if st.session_state.agent_index == -1:
        return

    client = st.session_state.data_chat_client 
    agent = st.session_state.agents[st.session_state.agent_index]
    project_id = st.session_state.project_id

    try:
        # TODO: get filter property on request to work
        request = geminidataanalytics.ListConversationsRequest(
            parent=f"projects/{project_id}/locations/global",
            page_size=100,
        )

        convos = list(client.list_conversations(request=request))
        convos = [c for c in convos if c.agents[0] == agent.name]
        st.session_state.convos = convos if len(convos) > 0 else []
        if rerun:
            st.rerun()

    except google_exceptions.GoogleAPICallError as e:
        st.error(f"API error fetching convos: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")

# Fetch messages for selected convo 
def fetch_messages_state(rerun=True):
    if st.session_state.convo_index == -1:
        return
    
    client = st.session_state.data_chat_client 
    convo = st.session_state.convos[st.session_state.convo_index]
    request = geminidataanalytics.ListMessagesRequest(parent=convo.name)

    try:
        msgs = list(client.list_messages(request=request))
        msgs = [m.message for m in msgs]
        st.session_state.convo_messages = list(reversed(msgs)) if len(msgs) > 0 else []
        if rerun:
            st.rerun()
    except google_exceptions.GoogleAPICallError as e:
        st.error(f"API error fetching messages: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}") 

# Changes agent index, fetches convos, clears or defaults convo index to 0 
def change_agent(agent_index):
    st.session_state.agent_index = agent_index
    st.session_state.convo_index = -1
    st.session_state.convo_messages = []
    fetch_convos_state(rerun=False)
    if st.session_state.convos:
        change_convo(0)
    
# Changes convo index, clears messages, and fetch messages
def change_convo(convo_index):
    st.session_state.convo_index = convo_index
    st.session_state.convo_messages = []
    fetch_messages_state(rerun=False)
 
def create_convo():
    if st.session_state.agent_index == -1:
        return
    
    client = st.session_state.data_chat_client 
    project_id = st.session_state.project_id
    agent = st.session_state.agents[st.session_state.agent_index]

    conversation = geminidataanalytics.Conversation()
    conversation.agents = [agent.name]
    
    request = geminidataanalytics.CreateConversationRequest(
        parent=f"projects/{project_id}/locations/global",
        conversation=conversation,
    )

    try:
        convo = client.create_conversation(request=request)
        st.session_state.convos.append(convo)
        st.session_state.convo_index = len(st.session_state.convos) - 1
        st.session_state.convo_messages = []
    except google_exceptions.GoogleAPICallError as e:
        st.error(f"API error fetching messages: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}") 