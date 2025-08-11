import asyncio
import os
import streamlit as st
from dotenv import load_dotenv
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.oauth2 import GetAccessTokenError
from backend.auth import authenticate, get_user_data

load_dotenv(override=True)

REDIRECT_URI = "http://localhost:8501"



# just have this return true or false
def _authenticator():
    if "token" not in st.session_state:
        st.write("Please login")
        auth_url = asyncio.run(authenticate(
            REDIRECT_URI=REDIRECT_URI, oaclient=client))
        if auth_url:
            st.markdown(f"[Login with Google]({auth_url})")

        code = st.query_params.get("code")
        if code:
            try:
                token, email = asyncio.run(
                    get_user_data(
                        code,
                        REDIRECT_URI=REDIRECT_URI,
                        oaclient=client)
                )
                if token and email:
                    st.session_state.token = token
                    st.session_state.email = email
                    st.rerun()
            except GetAccessTokenError as e:
                print(e)
                st.write("not logged in yet")
    else:
        if "initialized" not in st.session_state:
            st.session_state.project_id = PROJECT_ID
            st.session_state.dataqna_project_id = "bigquery-public-data"
            st.session_state.dataset_id = "san_francisco"
            st.session_state.table_ids = ("street_trees",)
            st.session_state.system_instruction = "answer questions"
            st.session_state.initialized = True
            if "looker_host" not in st.session_state:
                st.session_state.looker_host = "www.demo.com"
            if "looker_secret" not in st.session_state:
                st.session_state.looker_secret = "fillin"
            if "looker_client_id" not in st.session_state:
                st.session_state.looker_client_id = "fillin"
            if "looker_explore" not in st.session_state:
                st.session_state.looker_explore = "fillin"
            if "looker_model" not in st.session_state:
                st.session_state.looker_model = "fillin"
            if "data_source" not in st.session_state:
                st.session_state.data_source = "BigQuery"
        pg = st.navigation([
                        st.Page("app_pages/config.py",
                                title="Agent Factory", icon="⚙️"),
                        st.Page("app_pages/chat.py",
                                title="Chat",
                                icon="🤖")])
        pg.run()

        # gimme_results = return_da_results(da_client=daclient)
        # st.write(gimme_results


def _auth_experience():
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
    st.sidebar.divider()


def main():
    st.title("""Conversational Analytics""")
    if _authenticator():
        _auth_experience()
main()
