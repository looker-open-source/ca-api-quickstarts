import streamlit as st
import os
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.oauth2 import GetAccessTokenError
from google.oauth2.credentials import Credentials
from typing import Optional
from dotenv import load_dotenv
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.oauth2 import GetAccessTokenError

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
] 

load_dotenv(override=True)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
PROJECT_ID = os.getenv("PROJECT_ID")

# Validate credentials
if not all((
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    REDIRECT_URI,
    PROJECT_ID
)):
    st.error("Missing required environment variables. Check .env file."
             f"Current variables {GOOGLE_CLIENT_ID=} "
             f"{GOOGLE_CLIENT_SECRET=} {REDIRECT_URI=} ")
    st.stop()

oauthClient = GoogleOAuth2(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)

async def getAuthUrl() -> Optional[str]:
    auth_url = await oauthClient.get_authorization_url(
        REDIRECT_URI,
        # TODO clean up scopes 
        scope=SCOPES,
        extras_params={"access_type": "offline"}
    )
    return auth_url

async def getCreds(
    code: str, 
) -> Optional[Credentials]:
    try:
        token = await oauthClient.get_access_token(code, REDIRECT_URI)
        if token:
            creds = Credentials(
                token=token["access_token"],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET,
                scopes=SCOPES,
            )
            return creds
    except GetAccessTokenError as e:
        st.error(f"Failed to get access token: {str(e)}")
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
    return None
