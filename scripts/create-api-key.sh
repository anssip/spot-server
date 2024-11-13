#!/bin/bash

PROJECT_ID="spotcanvas-prod"
LOCATION="europe-west1"

# Exit on any error
set -e

echo "Creating new API key for project: $PROJECT_ID"

# Create API key
# First retrieve the key by display name if it exists
API_KEY=$(gcloud alpha services api-keys list \
  --filter='displayName="Firebase Web Client Key"' \
  --format="value(name)" | head -n 1 | sed 's/.*keys\///')

if [ -z "$API_KEY" ]; then
  # Create API key as it doesn't exist
  API_KEY=$(gcloud alpha services api-keys create \
    --display-name="Firebase Web Client Key" \
    --api-target=service=firestore.googleapis.com \
    --project=$PROJECT_ID \
    --format="value(keyString)")
else
  # Get the existing API key string
  API_KEY=$(gcloud alpha services api-keys get-key-string ${API_KEY} \
    --project=$PROJECT_ID)
  echo "API key already exists"
fi

# Always ensure the secret exists
echo "Storing API key in Secret Manager..."
echo -n "$API_KEY" | \
gcloud secrets create firebase-api-key \
  --data-file=- \
  --project=$PROJECT_ID \
  --replication-policy="automatic" \
  || echo -n "$API_KEY" | \
     gcloud secrets versions add firebase-api-key \
     --data-file=- \
     --project=$PROJECT_ID

echo "API key created and stored in Secret Manager"
echo "You can retrieve it using: gcloud secrets versions access latest --secret=firebase-api-key" 