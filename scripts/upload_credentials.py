import os
from google.cloud import secretmanager
import json
import google.auth
from google.auth.transport.requests import Request

def upload_service_account_key():
    # Read the service account key file
    with open('serviceAccountKey.json', 'r') as f:
        secret_content = f.read()

    # Create the secret manager client with explicit credentials
    credentials, project = google.auth.default()
    credentials.refresh(Request())
    client = secretmanager.SecretManagerServiceClient(credentials=credentials)

    # Get project ID from environment
    project_id = os.environ.get('PROJECT_ID')

    if not project_id:
        raise ValueError("PROJECT_ID environment variable is not set")
    
    # Create secret
    parent = f"projects/{project_id}"
    secret_id = "firestore-sa"

    try:
        # First create the secret
        secret = client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {"replication": {"automatic": {}}},
            }
        )
        print(f"Created secret: {secret.name}")
    except Exception as e:
        print(f"Secret might already exist: {e}")

    # Add the secret version
    parent = client.secret_path(project_id, secret_id)
    
    payload = secret_content.encode('UTF-8')
    
    version = client.add_secret_version(
        request={
            "parent": parent,
            "payload": {"data": payload},
        }
    )
    
    print(f"Added secret version: {version.name}")

if __name__ == "__main__":
    upload_service_account_key() 