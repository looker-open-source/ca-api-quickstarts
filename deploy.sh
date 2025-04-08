# ------------------------------------------
# Provided by the user: begin
# ------------------------------------------
PROJECT_ID=""
DATASTORE_PROJECT_ID=""
REGION="us-central1"
GOOGLE_CLIENT_ID=""
GOOGLE_CLIENT_SECRET=""
GEMINI_REGION = "us-central1"
BQ_LOCATION = "us"
MODEL = "gemini-2.0-flash-001"
TEMPERATURE = 0.2
TOP_P = 0.7
# ------------------------------------------
# Provided by the user: end
# ------------------------------------------


TIMESTAMP=$(date +%Y%m%d%H%M%S)
DOCKER_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/cortado-docker-repo/cortado-app:${TIMESTAMP}"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
APP_NAME="cortado-${TIMESTAMP}"
REDIRECT_URI="https://${APP_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"

echo "Creating Artifact Registry repository..."
if ! gcloud artifacts repositories describe cortado-docker-repo --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "Creating Artifact Registry repository..."
  gcloud artifacts repositories create cortado-docker-repo --repository-format=docker --location="${REGION}" --project="${PROJECT_ID}"
else
  echo "Artifact Registry repository already exists."
fi

gcloud builds submit --project=${PROJECT_ID} --tag ${DOCKER_IMAGE}

echo "Deploying Cortado app on Cloud Run"
cd terraform

cat <<EOF > terraform.tfvars
project_id           = "${PROJECT_ID}"
region               = "${REGION}"
datastore_project_id = "${DATASTORE_PROJECT_ID}"
app_name             = "${APP_NAME}"
image                = "${DOCKER_IMAGE}"
redirect_uri         = "${REDIRECT_URI}"
google_client_id     = "${GOOGLE_CLIENT_ID}"
google_client_secret = "${GOOGLE_CLIENT_SECRET}"
EOF

# Display terraform.tfvars for verification
echo "Contents of terraform.tfvars:"
cat terraform.tfvars

terraform init
terraform apply --auto-approve

echo "Deployment Complete"
echo "To enable access to your application, please add the provided URI to both the Authorized JavaScript origins and Authorized redirect URIs within your OAuth 2.0 Client ID configuration. Once registered, you can access the application using this URI."
echo "${REDIRECT_URI}"
