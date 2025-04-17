import looker_sdk
import logging
import os


def check_credentials(host: str, client_id: str, client_secret: str):
    os.environ["LOOKERSDK_BASE_URL"] = host
    # If your looker URL has .cloud in it (hosted on GCP), do not include :19999 (ie: https://your.cloud.looker.com).
    os.environ["LOOKERSDK_API_VERSION"] = "4.0"
    # 3.1 is the default version. You can change this to 4.0 if you want.
    os.environ["LOOKERSDK_VERIFY_SSL"] = "true"
    # Defaults to true if not set. SSL verification should generally be on unless you have a real good reason not to use it. Valid options: true, y, t, yes, 1.
    os.environ["LOOKERSDK_TIMEOUT"] = "120"
    # Seconds till request timeout. Standard default is 120.

    # Get the following values from your Users page in the Admin panel of your Looker instance > Users > Your user > Edit API keys. If you know your user id, you can visit https://your.looker.com/admin/users/<your_user_id>/edit.
    os.environ["LOOKERSDK_CLIENT_ID"] = client_id
    # No defaults.
    os.environ["LOOKERSDK_CLIENT_SECRET"] = client_secret
    # No defaults. This should be protected at all costs. Please do not leave it sitting here, even if you don't share this document.

    try:
        # Attempt to initialize the SDK (ensure your config is set up)
        sdk = looker_sdk.init40()  # or init31() for v3.1
        logging.info("Looker SDK initialized successfully.")

        # Attempt to get the current user
        my_user = sdk.me()
        logging.info(f"Successfully fetched user: {my_user.id}")
        logging.info(f"logged in as {my_user.first_name}")

        return 200, sdk

    except Exception as e:
        # Handle any error during initialization or the 'me()' call
        logging.error(f"An error occurred with the Looker SDK: {e}")
        # sdk and my_user will remain None (or their initial value if init succeeded but me() failed)
        # Add any specific error handling logic here (e.g., exit script, return error status)

        return 400, "Authentication failed"


def get_looker_models(sdk):
    list_of_models = []
    models = sdk.all_lookml_models(
                  exclude_empty=True,
                  exclude_hidden=True,
                  include_internal=False)
    for m in models:
        list_of_models.append(m.name)

    return list_of_models


def get_looker_explores(sdk, model):
    model = sdk.lookml_model(lookml_model_name=model)
    explores = []
    for e in model.explores:
        explores.append(e.name)
    return explores
