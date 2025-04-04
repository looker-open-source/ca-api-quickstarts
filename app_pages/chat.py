import streamlit as st
import pandas as pd
from backend import dataqna
from app_pages.utils import display_dataqna_conversation
from google.cloud import dataqna_v1alpha1
import os
from app_pages.config import (
    CONFIG_PROJECT_ID,
    CONFIG_DATASET_ID,
    CONFIG_SELECTED_TABLES_INFO,
    CONFIG_SYSTEM_INSTRUCTIONS
)

DATASTORE_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")

def chat():
    # Add unique keys to buttons
    if st.sidebar.button("Logout", key="logout_button"):
        st.session_state.clear()
        st.rerun()
    st.sidebar.divider()
    
    if ("messages" not in st.session_state or
            not isinstance(st.session_state.messages, list)):
        st.session_state.messages = []

    # Check for required configuration
    if not st.session_state.get(CONFIG_PROJECT_ID) or not st.session_state.get(CONFIG_DATASET_ID):
        st.warning("Please go back to the Agent Factory to configure your data source.")
        if st.button("Go to Agent Factory", key="config_button_1"):
            st.switch_page("app_pages/config.py")
        return

    selected_tables = st.session_state.get(CONFIG_SELECTED_TABLES_INFO, [])
    if not selected_tables:
        st.warning("Please select at least one table in the Agent Factory.")
        if st.button("Go to Agent Factory", key="config_button_2"):
            st.switch_page("app_pages/config.py")
        return

    # Initialize system instructions if not present
    if CONFIG_SYSTEM_INSTRUCTIONS not in st.session_state:
        st.session_state[CONFIG_SYSTEM_INSTRUCTIONS] = "You are a helpful data analysis assistant."

    # Display current configuration with expander
    with st.expander("Current Agent Configuration 🔍", expanded=False):
        st.subheader("Data Source")
        dataqna_config_table = pd.DataFrame({
            "Project": [st.session_state[CONFIG_PROJECT_ID]],
            "Dataset": [st.session_state[CONFIG_DATASET_ID]],
            "Tables": [[table_info['table'] for table_info in selected_tables]],
        })
        st.table(dataqna_config_table)
        
        # Display system instructions
        st.subheader("System Instructions")
        system_instruction = st.session_state[CONFIG_SYSTEM_INSTRUCTIONS]  # Direct access instead of .get()
        if system_instruction and system_instruction.strip():  # Check if not empty
            st.code(system_instruction, language="yaml")
            # Pass to response generation
            system_instructions_for_api = system_instruction
        else:
            st.info("No system instructions configured.")
            system_instructions_for_api = "You are a helpful data analysis assistant."  # Default fallback
            
        # Show individual table details
        st.subheader("Selected Tables")
        for table_info in selected_tables:
            st.markdown(f"- **{table_info['table']}**")

    # Display chat messages from history on app rerun
    display_dataqna_conversation.display_dataqna_messages(
        st.session_state.messages)

    # React to user input
    if prompt := st.chat_input("What would you like to know about your data?"):
        # Create user message and add to chat history
        user_message = dataqna_v1alpha1.Message()
        user_message.user_message.text = prompt
        display_dataqna_conversation.display_dataqna_message(user_message)
        st.session_state.messages.append(user_message)

        # Call the api with updated session variables
        response = dataqna.generate_response(
            st.session_state.messages,
            st.session_state[CONFIG_PROJECT_ID],
            DATASTORE_PROJECT_ID,  # Using env var for dataqna project
            st.session_state[CONFIG_DATASET_ID],
            [table_info['table'] for table_info in selected_tables],
            st.session_state.token,
            system_instruction=system_instructions_for_api
        )
        
        for message in response:
            display_dataqna_conversation.display_dataqna_message(message)
            st.session_state.messages.append(message)

if "token" not in st.session_state:
    st.switch_page("app.py")
else:
    chat()
