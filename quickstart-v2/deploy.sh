set -e

PROJECT_ID="bp-steveswalker-solutions-303"
REGION="us-central1"
REPOSITORY="my-repo"
IMAGE_NAME="gilligan"
SERVICE_NAME="ca-api-quickstart-v2"

SERVICE_ACCOUNT_EMAIL="da-tco-app@bp-steveswalker-solutions-303.iam.gserviceaccount.com" 

IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest"

echo "STEP 1: Building the Docker image..."
docker build -t "$IMAGE_TAG" .

echo "STEP 2: Pushing the image to Artifact Registry..."
docker push "$IMAGE_TAG"


echo "STEP 3: Deploying to Cloud Run..."
gcloud alpha run deploy "$SERVICE_NAME" \
  --image "$IMAGE_TAG" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --iap \
  --no-allow-unauthenticated \
  --service-account "$SERVICE_ACCOUNT_EMAIL"

echo "✅ Deployment complete!"


