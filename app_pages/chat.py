import streamlit as st
from google.cloud import geminidataanalytics
from state import create_convo, fetch_convos_state, fetch_messages_state
from utils.chat import show_message

AGENT_SELECT_KEY = "agent_selectbox_value"
CONVO_SELECT_KEY = "agent_convo_value"

def handle_agent_select():
    state = st.session_state
    state.current_agent = state[AGENT_SELECT_KEY]
    state.current_convo = None
    state.convo_messages = []
    st.spinner("Fetching past conversations")
    fetch_convos_state(state.current_agent, False)
    if len(state.convos) > 0:
        st.spinner("Fetching last conversation's messages")
        state.current_convo = state.convos[0]
        fetch_messages_state(state.current_convo, False)

def handle_convo_select():
    state = st.session_state
    state.current_convo = state[CONVO_SELECT_KEY]
    state.convo_messages = []
    st.spinner("Fetching past message")
    fetch_messages_state(state.current_convo, False)

def handle_create_convo():
    state = st.session_state
    st.spinner("Creating new convo")
    state.current_convo = create_convo(agent=state.current_agent)
    state.convo_messages = []

def conversations_main():
    state = st.session_state

    if len(state.agents) == 0:
        st.warning("Please create an agent first before chatting")
        st.stop()

    # Select Agent/Conversation dropdown bar
    with st.container(
        border=True,
        horizontal=True,
        horizontal_alignment="distribute"
    ):
        def get_agent_display_name(a):
            """Returns the agent's display name, or a fallback from its resource name."""
            return getattr(a, 'display_name', None) or a.name.split('/')[-1]
        sorted_agents = sorted(state.agents, key=get_agent_display_name)

        agent_index = None
        if state.current_agent:
            for index, agent in enumerate(sorted_agents):
                if state.current_agent.name == agent.name:
                    agent_index = index
            if agent_index is None:
                state.current_agent = None
                state.current_convo = None
                state.convo_messages = []

        st.selectbox(
            "Select agent to chat with:",
            sorted_agents,
            index=agent_index,
            key=AGENT_SELECT_KEY,
            format_func=get_agent_display_name,
            on_change=handle_agent_select
        )

        convo_index = None
        if state.current_convo:
            for index, convo in enumerate(state.convos):
                if state.current_convo.name == convo.name:
                    convo_index = index

        st.selectbox(
            "Select previous conversation with agent (by last used):",
            state.convos,
            index=convo_index,
            key=CONVO_SELECT_KEY,
            format_func=lambda c: c.last_used_time.strftime("%m/%d/%Y, %H:%M:%S"),
            on_change=handle_convo_select
        )
        st.button(
            "Start new conversation with agent",
            on_click=handle_create_convo,
            disabled=len(state.agents) == 0
        )

    # Chat
    subheader_string = "Chat"
    if state.current_convo:
        subheader_string = f'Chat - Conversation started at {state.current_convo.create_time.strftime("%m/%d/%Y, %H:%M:%S")}'

    st.subheader(subheader_string)

    if state.current_agent is None:
        st.warning("Please select an agent above to chat with")
        st.stop()

    # Chat history
    for message in state.convo_messages:
        if "system_message" in message:
            with st.chat_message("assistant"):
                show_message(message)
        else:
            with st.chat_message("user"):
                st.markdown(message.user_message.text)


    # Chat input
    user_input = st.chat_input("What would you like to know?")

    if user_input:
        if len(state.convos) == 0:
            handle_create_convo()
        # Record user message
        state.convo_messages.append(geminidataanalytics.Message(user_message={"text": user_input}))
        with st.chat_message("user"):
            st.markdown(user_input)

        # Assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking... 🤖"):
                user_msg = geminidataanalytics.Message(user_message={"text": user_input})
                convo_ref = geminidataanalytics.ConversationReference()
                convo_ref.conversation = state.current_convo.name
                convo_ref.data_agent_context.data_agent = state.current_agent.name

                if is_looker_agent(state.current_agent):
                    credentials = geminidataanalytics.Credentials()
                    credentials.oauth.secret.client_id = st.secrets.looker.client_id
                    credentials.oauth.secret.client_secret = st.secrets.looker.client_secret
                    convo_ref.data_agent_context.credentials = credentials


                req = geminidataanalytics.ChatRequest(
                    parent=f"projects/{st.secrets.cloud.project_id}/locations/global",
                    messages=[user_msg],
                    conversation_reference=convo_ref,
                )
                for message in state.chat_client.chat(request=req):
                    show_message(message)
                    state.convo_messages.append(message)
            st.rerun()

def is_looker_agent(agent) -> bool:
    datasource_references = agent.data_analytics_agent.published_context.datasource_references

    return "looker" in datasource_references

conversations_main()
