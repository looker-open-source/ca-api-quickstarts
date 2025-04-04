import streamlit as st
from google.oauth2.credentials import Credentials
import asyncio
import os
from google.cloud import datastore
from dotenv import load_dotenv


def setup_datastore_client(
        token,
        DATASTORE_PROJECT_ID,
        GOOGLE_CLIENT_ID,
        GOOGLE_CLIENT_SECRET):
    """Create Datastore client using OAuth token"""
    credentials = Credentials(
        token=token['access_token'],
        # refresh_token=token['refresh_token'],
        token_uri='https://oauth2.googleapis.com/token',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=['https://www.googleapis.com/auth/datastore']
        # Add scope here too

    )

    return datastore.Client(
        project=DATASTORE_PROJECT_ID,
        credentials=credentials
    )


def get_datastore_email(da_client):
    kind = "Users"
    # The name/ID for the new entity
    name = st.session_state.email
    # The Cloud Datastore key for the new entity
    task_key = da_client.key(kind, name)

    # Prepares the new entity
    task = datastore.Entity(key=task_key)
    task["schema"] = """
    asdfafa
    adfafa
    adfasfasdf
    adfasf
    adfadf
    adfad
    """

    # Saves the entity
    da_client.put(task)

    print(f"Saved {task.key.name}: {task['email']}")


def return_da_results(da_client):
    kind = "Users"
    # The name/ID for the new entity
    name = st.session_state.email
    # The Cloud Datastore key for the new entity
    task_key = da_client.key(kind, name)

    task = da_client.get(task_key)
    return task
