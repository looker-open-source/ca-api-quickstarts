# Stage 1: "builder" - Use an official image with gcloud to download the file
FROM google/cloud-sdk:slim as builder



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


COPY . .

EXPOSE 8080

CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]

