#!/bin/bash

PROJECT_ID="spotcanvas-prod"
REGION="europe-west1"

# Exit on any error
set -e

# Ensure Cloud Build is set up correctly
chmod +x scripts/setup-cloud-build.sh
./scripts/setup-cloud-build.sh

echo "Deploying using Cloud Build..."

# Submit the build to Cloud Build with explicit substitutions
gcloud builds submit \
    --config cloudbuild.yaml \
    --substitutions=_REGION=$REGION

echo "Deployment complete!" 