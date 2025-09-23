import streamlit as st
from state import init_state

def _init():
    if "initialized" not in st.session_state:
        with st.spinner("Loading"):
            init_state()
    else:
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
