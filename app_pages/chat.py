import streamlit as st
import pandas as pd
from backend import dataqna
from app_pages.utils import display_dataqna_conversation
from google.cloud import dataqna_v1alpha1


def chat():
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
    st.sidebar.divider()
    if ("messages" not in st.session_state or
            not isinstance(st.session_state.messages, list)):
        st.session_state.messages = []
    if "dataset_id" not in st.session_state:
        st.text("Please go back to the Agent factory and select a dataset")

    if len(st.session_state.table_ids) == 0:
        st.text("""Please click Agent Factory and select at least one table""")

    if "dataset_id" and "dataqna_project_id" in st.session_state and len(st.session_state.table_ids) > 0:

        dataqna_config_table = pd.DataFrame(
                                        {
                                            "Project": [st.session_state.dataqna_project_id],
                                            "Dataset": [st.session_state.dataset_id],
                                            "Tables": [st.session_state.table_ids],
                                        })
        st.table(dataqna_config_table)
        if 'system_instruction' not in st.session_state:
            st.session_state.system_instruction = ""
        # st.code(st.session_state.system_instruction)



    # Display chat messages from history on app rerun
    display_dataqna_conversation.display_dataqna_messages(
        st.session_state.messages)

    # React to user input
    if prompt := st.chat_input("What is up?"):
        # Create user message and add to chat history
        user_message = dataqna_v1alpha1.Message()
        user_message.user_message.text = prompt
        display_dataqna_conversation.display_dataqna_message(user_message)
        st.session_state.messages.append(user_message)

        # Call the api
        response = dataqna.generate_response(
             st.session_state.messages, st.session_state.project_id,
             st.session_state.dataqna_project_id,
             st.session_state.dataset_id, st.session_state.table_ids,
             st.session_state.token,
             system_instruction=st.session_state.system_instruction)
        for message in response:
            display_dataqna_conversation.display_dataqna_message(message)
            st.session_state.messages.append(message)


if "token" not in st.session_state:
    st.switch_page("app.py")
else:
    chat()
