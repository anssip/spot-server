#!/bin/bash

PROJECT_ID="spotcanvas-prod"
REGION="europe-west1"

# Exit on any error
set -e

# Enable required APIs
gcloud services enable cloudbuild.googleapis.com --project=$PROJECT_ID
gcloud services enable run.googleapis.com --project=$PROJECT_ID
gcloud services enable artifactregistry.googleapis.com --project=$PROJECT_ID

# Create Artifact Registry repository if it doesn't exist
gcloud artifacts repositories create spot-server \
    --repository-format=docker \
    --location=$REGION \
    --project=$PROJECT_ID \
    || true  # Continue if repository already exists

# Get the Cloud Build service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

# Grant necessary permissions to Cloud Build
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUDBUILD_SA}" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUDBUILD_SA}" \
    --role="roles/artifactregistry.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUDBUILD_SA}" \
    --role="roles/iam.serviceAccountUser"

# Create initial services with minimal configuration
for i in {0..9}; do
    SERVICE_NAME="spot-server-shard-$i"
    
    # Create an initial minimal service if it doesn't exist
    gcloud run deploy $SERVICE_NAME \
        --image="gcr.io/cloudrun/hello" \
        --region=$REGION \
        --project=$PROJECT_ID \
        --port=8080 \
        --memory=512Mi \
        --timeout=300s \
        --platform=managed \
        --quiet \
        || true  # Continue if service already exists
    
    # Set IAM policy
    gcloud run services add-iam-policy-binding $SERVICE_NAME \
        --member="allUsers" \
        --role="roles/run.invoker" \
        --region=$REGION \
        --project=$PROJECT_ID \
        || true
done

echo "Cloud Build setup complete!" 