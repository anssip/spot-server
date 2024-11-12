#! /bin/bash

PROJECT_ID="spotcanvas-prod"

# Exit on any error
set -e

# Check if service account already exists
if gcloud iam service-accounts describe "my-firestore-sa@$PROJECT_ID.iam.gserviceaccount.com" &>/dev/null; then
    echo "Service account already exists"
else
    gcloud iam service-accounts create my-firestore-sa \
        --display-name "Spot Server Service Account" \
        --project=$PROJECT_ID
fi

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:my-firestore-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

gcloud iam service-accounts keys create serviceAccountKey.json \
    --iam-account=my-firestore-sa@$PROJECT_ID.iam.gserviceaccount.com
