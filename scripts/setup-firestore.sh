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

    # Set up some basic Firestore rules
    cat > firestore.rules << EOL
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if false;  // Secure by default, only allow access through service account
    }
  }
}
EOL
    # Deploy Firestore rules
    gcloud firestore rules deploy firestore.rules \
        --project=$PROJECT_ID

    echo "Firestore setup complete!"
}

# Check if the database already exists
if gcloud firestore databases describe --project=$PROJECT_ID &>/dev/null; then
    echo "Firestore database already exists."
else
    echo "Setting up Firestore for project: $PROJECT_ID"
    setup_firestore
fi

echo "Setup complete! Collections will be created automatically when data is first written."