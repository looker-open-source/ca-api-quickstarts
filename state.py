import streamlit as st
from google.cloud import geminidataanalytics
from google.api_core import exceptions as google_exceptions

# Only runs once for whole session
def init_state():
    state = st.session_state

    state.agents = []
    state.convos = []
    state.convo_messages = []

    state.agent_client = geminidataanalytics.DataAgentServiceClient()
    state.chat_client = geminidataanalytics.DataChatServiceClient()

    fetch_agents_state(rerun=False)

    state.current_agent = None
    if state.agents:
        state.current_agent = state.agents[-1]

    if state.current_agent:
        fetch_convos_state(agent=state.current_agent, rerun=False)

    state.current_convo = None
    if state.convos :
        state.current_convo = state.convos[0]

    if state.current_convo:
        fetch_messages_state(convo=state.current_convo, rerun=False)

    state.initialized = True
    st.rerun()

# fetch all agents
def fetch_agents_state(rerun=True):
    state = st.session_state
    client = state.agent_client
    project_id = st.secrets.cloud.project_id

    try:
        request = geminidataanalytics.ListDataAgentsRequest(
            parent=f"projects/{project_id}/locations/global"
        )
        agents = list(client.list_data_agents(request=request))
        state.agents = agents if len(agents) > 0 else []
        if rerun:
            st.rerun()
    except google_exceptions.GoogleAPICallError as e:
        st.error(f"API error fetching agents: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")

# Limited to fetching 100 conversations from selected agent
def fetch_convos_state(agent=None, rerun=True):
    if agent is None:
        return

    state = st.session_state
    state.convos = []
    client = state.chat_client
    project_id = st.secrets.cloud.project_id

    try:
        # TODO: get filter property on request to work
        request = geminidataanalytics.ListConversationsRequest(
            parent=f"projects/{project_id}/locations/global",
            page_size=100,
        )

        convos = list(client.list_conversations(request=request))
        convos = [c for c in convos if c.agents[0] == agent.name]
        state.convos = convos if len(convos) > 0 else []
        if rerun:
            st.rerun()

    except google_exceptions.GoogleAPICallError as e:
        st.error(f"API error fetching convos: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")

# Fetch messages for selected convo
def fetch_messages_state(convo=None, rerun=True):
    if convo is None:
        return

    state = st.session_state
    state.convo_messages = []
    client = state.chat_client
    request = geminidataanalytics.ListMessagesRequest(parent=convo.name)

    try:
        msgs = list(client.list_messages(request=request))
        msgs = [m.message for m in msgs]
        state.convo_messages = list(reversed(msgs)) if len(msgs) > 0 else []
        if rerun:
            st.rerun()
    except google_exceptions.GoogleAPICallError as e:
        st.error(f"API error fetching messages: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")

# Creates new convo, appends to current convos
def create_convo(agent=None):
    state = st.session_state
    client = state.chat_client
    project_id = st.secrets.cloud.project_id

    conversation = geminidataanalytics.Conversation()
    conversation.agents = [agent.name]

    request = geminidataanalytics.CreateConversationRequest(
        parent=f"projects/{project_id}/locations/global",
        conversation=conversation,
    )

    try:
        convo = client.create_conversation(request=request)
        state.convos.insert(0, convo)
        return convo
    except google_exceptions.GoogleAPICallError as e:
        st.error(f"API error creating convo: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
