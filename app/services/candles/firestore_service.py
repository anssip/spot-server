import os
from firebase_admin import credentials, firestore, initialize_app
from datetime import datetime
import time
from google.cloud import secretmanager
from google.oauth2 import service_account
import json


class FirestoreService:
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
        self.db = firestore.client()

    async def update_live_candle(self, product_id: str, candle_data: list):
        """
        Updates the live candle document for a specific product

        candle_data format: [timestamp, low, high, open, close, volume]
        """
        timestamp, low, high, open_price, close, volume = candle_data

        # Convert timestamp to start of minute to match candle interval
        candle_start = int(timestamp - (timestamp % 60)
                           )  # Round to nearest minute

        live_candle_ref = self.db.collection(
            'live_candles').document(product_id)

        live_candle = {
            'timestamp': candle_start,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'lastUpdate': firestore.SERVER_TIMESTAMP,
            'productId': product_id
        }

        # Use set with merge=True to update fields without overwriting the entire document
        live_candle_ref.set(live_candle, merge=True)

    async def store_completed_candle(self, product_id: str, candle_data: list):
        """
        Stores a completed candle in the historical candles collection
        """
        timestamp, low, high, open_price, close, volume = candle_data
        candle_start = int(timestamp - (timestamp % 60))

        # Create a document ID using timestamp and product_id
        doc_id = f"{product_id}-{candle_start}"

        historical_candle = {
            'timestamp': candle_start,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'productId': product_id
        }

        self.db.collection('historical_candles').document(
            doc_id).set(historical_candle)
