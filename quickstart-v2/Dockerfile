# Stage 1: "builder" - Use an official image with gcloud to download the file
FROM google/cloud-sdk:slim as builder

# Define the GCS path as a build argument
ARG GCS_FILE_PATH=gs://chill_demo/geminidataanalytics-v1alpha-py.tar.gz



WORKDIR /sdk

# Download the file from GCS.
# This requires the build environment (e.g., Cloud Build, or local gcloud auth)
# to have credentials to access the GCS bucket.
RUN gcloud storage cp ${GCS_FILE_PATH} ./sdk.tar.gz


# Stage 2: "final" - The actual application image
FROM python:3.10-slim

# Install only the necessary runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev zlib1g-dev libpng-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install them first (for layer caching)
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the downloaded SDK from the "builder" stage and install it
COPY --from=builder /sdk/sdk.tar.gz /tmp/sdk.tar.gz
RUN pip install /tmp/sdk.tar.gz && \
    rm /tmp/sdk.tar.gz

# Copy the rest of the app source code
COPY . .

EXPOSE 8080

CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]

