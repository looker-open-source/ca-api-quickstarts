from google.cloud import secretmanager


def get_secret(project_id: str, secret_id: str, version_id: str = "latest") -> str:
    """
    Retrieves a secret from Google Cloud Secret Manager.
    Args:
        project_id (str): The Google Cloud project ID.
        secret_id (str): The ID of the secret to retrieve.
        version_id (str): The version of the secret to retrieve. Defaults to "latest".
    Returns:
        str: The secret payload as a string.
    Raises:
        Exception: If the secret cannot be retrieved.
    """
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")
