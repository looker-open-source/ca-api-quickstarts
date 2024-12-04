# Streamlit

## Overview

This app helps to run streamlit locally to test DataQnA.

## Requirements

- Please see requirements.txt

- Ensure your are [authenticated](https://cloud.google.com/docs/authentication/provide-credentials-adc#local-dev) via [gcloud](https://cloud.google.com/sdk/docs/install)

- add the billing project id to the code where the comment `# ADD YOUR BILLING PROJECT` indicates

## Setup

`streamlit run main.py`

### Additional option

If you want to add more public or private datasets, add these to the datasets object at the beginning of the code and enhance the `st.selectbox`

If you want to run the streamlit app on App Engine with GCP:

- Add an app.yaml file to your directory and add the code below

```yaml
runtime: python
runtime_config:
  operating_system: ubuntu22
  runtime_version: 3.10.0
entrypoint: streamlit run --server.port=8080 --server.address=0.0.0.0 --server.enableCORS=false --server.enableWebsocketCompression=false --server.enableXsrfProtection=false --server.headless=true main.py
env: flex
network:
  session_affinity: true
```

- Ensure the Service Account use by AppEngine has the right permissions (BQ and CloudCompanion User)
- deploy via `gcloud app deploy`
