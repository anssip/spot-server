import os
from firebase_admin import credentials, firestore, initialize_app
from datetime import datetime
import time
from google.cloud import secretmanager
from google.oauth2 import service_account
import json
from app.services.db.db_helper import DbHelper


class FirestoreService:
    def __init__(self):
        self.db_helper = DbHelper()
        self.db = self.db_helper.get_client()

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
