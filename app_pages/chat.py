import os
import streamlit as st
from google.cloud import geminidataanalytics
from state import change_agent, change_convo, create_convo
from datetime import datetime
from utils.chat import show_message

AGENT_SELECT_KEY = "agent_selectbox_value"
CONVO_SELECT_KEY = "agent_convo_value"

def handle_agent_select():
    index = 0
    for i, a in enumerate(st.session_state.agents):
        if a.name == st.session_state[AGENT_SELECT_KEY].name:
            index = i 
    change_agent(index)

def handle_convo_select():
    index = 0
    for i, c in enumerate(st.session_state.agents):
        if c.name == st.session_state[CONVO_SELECT_KEY].name:
            index = i 
    change_convo(index)

def conversations_main():
    with st.container(
        border=True, 
        horizontal=True, 
        horizontal_alignment="distribute"
    ):
        agent_index = st.session_state.agent_index
        convo_index = st.session_state.convo_index

        st.selectbox(
            "Select agent",
            st.session_state.agents,
            index=agent_index,
            key=AGENT_SELECT_KEY,
            format_func=lambda a: a.display_name,
            on_change=handle_agent_select
        )
        st.selectbox(
            "Select conversation with agent",
            st.session_state.convos,
            index=convo_index if convo_index > 0 else 0,
            key=CONVO_SELECT_KEY,
            format_func=lambda c: c.last_used_time.strftime("%m/%d/%Y, %H:%M:%S"),
            on_change=handle_convo_select
        )
        st.button(
            "Create new conversation with agent",
            on_click=create_convo
        )

    # with chat:
    st.subheader("Chat")

    # Chat history
    for message in st.session_state.convo_messages:
        if "system_message" in message:
            with st.chat_message("assistant"):
                show_message(message)
        else:
            with st.chat_message("user"):
                st.markdown(message.user_message.text)

    # Chat input
    user_input = st.chat_input("What would you like to know?")

    if user_input:
        # Record user message
        st.session_state.convo_messages.append(geminidataanalytics.Message(user_message={"text": user_input}))
        with st.chat_message("user"):
            st.markdown(user_input)

        # Assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking... 🤖"):
                current_convo = st.session_state.convos[st.session_state.convo_index]
                current_agent = st.session_state.agents[st.session_state.agent_index]
                project_id = st.session_state.project_id
                client = st.session_state.data_chat_client

                user_msg = geminidataanalytics.Message(user_message={"text": user_input})
                convo_ref = geminidataanalytics.ConversationReference(
                    conversation=current_convo.name,
                    data_agent_context={
                        "data_agent": current_agent.name
                    },
                )
                req = geminidataanalytics.ChatRequest(
                    parent=f"projects/{project_id}/locations/global",
                    messages=[user_msg],
                    conversation_reference=convo_ref,
                )
                for message in client.chat(request=req):
                    show_message(message)
                    st.session_state.convo_messages.append(message)
            st.rerun()

conversations_main()
