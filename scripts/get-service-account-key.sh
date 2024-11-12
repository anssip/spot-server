PROJECT_ID="spotcanvas-prod"

gcloud iam service-accounts keys create serviceAccountKey.json \
    --iam-account=my-firestore-sa@$PROJECT_ID.iam.gserviceaccount.com
