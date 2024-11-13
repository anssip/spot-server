#!/bin/bash

PROJECT_ID="spotcanvas-prod"
LOCATION="europe-west1"

# Exit on any error
set -e

# Check if the service account exists
if ! gcloud iam service-accounts describe "my-firestore-sa@$PROJECT_ID.iam.gserviceaccount.com" &>/dev/null; then
    echo "Service account does not exist. Please create it first."
    exit 1
fi

setup_firestore() {
    # Enable the Firestore API
    gcloud services enable firestore.googleapis.com --project=$PROJECT_ID

    # Create Firestore database in Native mode
    gcloud firestore databases create \
        --project=$PROJECT_ID \
        --location=$LOCATION

    # Deploy Firestore rules
    firebase deploy --only firestore:rules --project=$PROJECT_ID

    echo "Firestore setup complete!"
}

# Check if the database already exists
if gcloud firestore databases describe --project=$PROJECT_ID &>/dev/null; then
    echo "Firestore database already exists."
    echo "Updating Firestore rules..."
    setup_firestore
else
    echo "Setting up Firestore for project: $PROJECT_ID"
    setup_firestore
fi

echo "Setup complete! Collections will be created automatically when data is first written."