import streamlit as st
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.oauth2 import GetAccessTokenError
from google.oauth2.credentials import Credentials
import asyncio
from typing import Tuple, Optional, Dict, Any


async def authenticate(REDIRECT_URI: str, oaclient: GoogleOAuth2) -> Optional[str]:
    """Authenticate user with Google OAuth2.
    
    Args:
        REDIRECT_URI: The OAuth2 redirect URI
        oaclient: Google OAuth2 client instance
    
    Returns:
        Optional[str]: Authorization URL if authentication needed, None otherwise
    """
    if "token" not in st.session_state:
        auth_url = await oaclient.get_authorization_url(
            REDIRECT_URI,
            scope=[
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile", 
                "https://www.googleapis.com/auth/datastore",
                "https://www.googleapis.com/auth/cloud-platform"
            ],
            extras_params={"access_type": "offline"}
        )
        return auth_url
    return None


async def get_user_data(
    code: str, 
    REDIRECT_URI: str, 
    oaclient: GoogleOAuth2
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Get user data from Google OAuth2 token.
    
    Args:
        code: OAuth2 authorization code
        REDIRECT_URI: The OAuth2 redirect URI
        oaclient: Google OAuth2 client instance
    
    Returns:
        Tuple containing the token dict and user email if successful, (None, None) otherwise
    """
    try:
        token = await oaclient.get_access_token(code, REDIRECT_URI)
        if token:
            user_id, email = await oaclient.get_id_email(token['access_token'])
            return token, email
    except GetAccessTokenError as e:
        st.error(f"Failed to get access token: {str(e)}")
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
    return None, None
