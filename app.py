import asyncio
import os

import streamlit as st
from dotenv import load_dotenv
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.oauth2 import GetAccessTokenError

from backend.auth import authenticate, get_user_data
from backend.datastore import return_da_results, setup_datastore_client
# https://github.com/readybuilderone/streamlit-multiplepage-simpleauth/blob/main/utils/menu.py
load_dotenv(override=True)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
DATASTORE_PROJECT_ID = os.getenv("PROJECT_ID")

# Validate credentials
if not all(
        (GOOGLE_CLIENT_ID,
            GOOGLE_CLIENT_SECRET,
            REDIRECT_URI,
            DATASTORE_PROJECT_ID)
):
    st.error("Missing required environment variables. Check .env file."
             f"Current variables {GOOGLE_CLIENT_ID=} "
             f"{GOOGLE_CLIENT_SECRET=} {REDIRECT_URI=} {DATASTORE_PROJECT_ID=}")
    st.stop()

client = GoogleOAuth2(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)


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
            st.session_state.project_id = DATASTORE_PROJECT_ID
            st.session_state.dataqna_project_id = "bigquery-public-data"
            st.session_state.dataset_id = "san_francisco"
            st.session_state.table_ids = ("street_trees",)
            st.session_state.system_instruction = "answer questions"
            st.session_state.initialized = True
        pg = st.navigation([
                        st.Page("app_pages/config.py",
                                title="Agent Factory", icon="⚙️"),
                        st.Page("app_pages/chat.py",
                                title="Chat",
                                icon="🤖")])
        pg.run()

        daclient = setup_datastore_client(
            token=st.session_state.token,
            DATASTORE_PROJECT_ID=DATASTORE_PROJECT_ID,
            GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID,
            GOOGLE_CLIENT_SECRET=GOOGLE_CLIENT_SECRET,
        )

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
