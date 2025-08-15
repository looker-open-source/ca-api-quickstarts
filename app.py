import asyncio
import streamlit as st
from utils.auth import getAuthUrl, getCreds
from state import init_state

def _init():
    if "creds" not in st.session_state:
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
            st.write("Welcome")
            # TODO: investigate if we need asyncio
            auth_url = asyncio.run(getAuthUrl())
            if auth_url:
                st.markdown(f'<a href="{auth_url}" target="_self">Please login with Google</a>', unsafe_allow_html=True)
    else:
        # Initialize state
        if "initialized" not in st.session_state:
            with st.spinner("Loading"):
                init_state()
        else:
            if st.sidebar.button("Logout"):
                st.session_state.clear()
                st.rerun()
            
            pg = st.navigation([
                            st.Page("app_pages/agents.py",
                                    title="Agents", icon="⚙️"),
                            st.Page("app_pages/chat.py",
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
