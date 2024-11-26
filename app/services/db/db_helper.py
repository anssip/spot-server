import os
import json
from firebase_admin import credentials, firestore, initialize_app
from google.cloud import secretmanager

class DbHelper:
    def __init__(self):
        env = os.getenv('ENVIRONMENT', 'development')
        
        if env == 'development':
            # Use local service account file for development
            cred = credentials.Certificate('serviceAccountKey.json')
        else:
            # Use Secret Manager for production
            secret_client = secretmanager.SecretManagerServiceClient()
            project_id = os.environ.get('PROJECT_ID')
            secret_name = f"projects/{project_id}/secrets/firestore-sa/versions/latest"
            response = secret_client.access_secret_version(request={"name": secret_name})
            secret_content = response.payload.data.decode("UTF-8")
            service_account_info = json.loads(secret_content)
            cred = credentials.Certificate(service_account_info)

        # Initialize Firebase Admin SDK
        initialize_app(cred)
        self.client = firestore.client()

    def get_client(self):
        return self.client