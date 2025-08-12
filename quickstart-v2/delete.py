import getpass
import streamlit as st


import os
import getpass
from typing import List
import google.auth
import streamlit as st
from dotenv import load_dotenv
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.api_core import exceptions as google_exceptions
from google.cloud import geminidataanalytics
from streamlit_extras.add_vertical_space import add_vertical_space
from error_handling import handle_errors, handle_streamlit_exception
import traceback

try:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.types import AgentInput
    adk_available = True
except Exception as e:
    adk_available = False
    st.exception(e, "line 26")
