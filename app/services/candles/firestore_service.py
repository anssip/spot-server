import os
from firebase_admin import credentials, firestore, initialize_app
from datetime import datetime
import time
from google.cloud import secretmanager
from google.oauth2 import service_account
import json
from app.services.db.db_helper import DbHelper

from dataclasses import dataclass
from typing import Literal
import logging

# Just get the logger, don't configure it
logger = logging.getLogger(__name__)

@dataclass
class Product:
    base_currency: str
    quote_currency: str
    last_updated: float
    source: str
    status: Literal["online", "delisted"]
    min_size: str = "0"
    max_size: str = "0"


class FirestoreService:
    _instance = None
    _db = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirestoreService, cls).__new__(cls)
            cls._instance.db_helper = DbHelper()
            cls._instance._db = cls._instance.db_helper.get_client()
        return cls._instance

    @property
    def db(self):
        return self._db

    async def update_live_candle(self, product_path: str, candle_data: list):
        """
        Updates the live candle document for a specific product under its exchange
        
        Args:
            product_path: Format "exchanges/{exchange}/products/{product_id}" 
                        or "exchanges/{exchange}/products/{product_id}/intervals/{interval}"
            candle_data: [timestamp, low, high, open, close, volume]
        """
        timestamp, low, high, open_price, close, volume = candle_data

        # Convert timestamp to start of minute
        candle_start = int(timestamp - (timestamp % 60))

        live_candle = {
            'timestamp': candle_start,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'lastUpdate': firestore.SERVER_TIMESTAMP,
        }

        # Split the path into segments and create document reference
        path_segments = product_path.split('/')
        doc_ref = self.db.document('/'.join(path_segments))
        
        # Use set with merge=True to update fields without overwriting the entire document
        doc_ref.set(live_candle, merge=True)

    async def get_products(self, exchange: str, status: Literal["online", "delisted"]) -> list[Product]:
        """
        Fetches products for a specific exchange with given status
        Only returns specific trading pairs: BTC-USD, ETH-USD, ADA-USD, DOGE-USD, SOL-USD
        """
        try:
            exchanges_ref = self.db.collection('trading_pairs').document('exchanges')
            exchanges_doc = exchanges_ref.get()
            
            if not exchanges_doc.exists:
                logger.error("Exchanges document not found")
                return []
            
            data = exchanges_doc.to_dict()
            products_map = data.get(exchange, {})
            
            # Debug logging
            logger.info(f"Raw products data for {exchange}, size: {len(products_map.keys())}")
            logger.info(f"Status filter: {status}")
            
            # Only get these specific trading pairs
            allowed_pairs = ["BTC-USD", "ETH-USD", "ADA-USD", "DOGE-USD", "SOL-USD"]
            
            products = []
            for product_id, product in products_map.items():
                # Skip if not in allowed pairs
                if product_id not in allowed_pairs:
                    continue
                    
                product_status = product.get('status')
                
                if product_status == status:
                    # Get timestamp from Firestore timestamp
                    timestamp = product['last_updated'].timestamp() if isinstance(product['last_updated'], datetime) else float(product['last_updated'])
                    
                    products.append(Product(
                        base_currency=product['base_currency'],
                        quote_currency=product['quote_currency'],
                        status=status,
                        min_size=str(product.get('min_size', '0')),
                        max_size=str(product.get('max_size', '0')),
                        last_updated=timestamp,
                        source=product_id
                    ))
            
            logger.info(f"Found {len(products)} filtered {status} products for {exchange} (limited to: {', '.join(allowed_pairs)})")
                
            return products
            
        except Exception as error:
            logger.error(f"Error fetching products: {error}", exc_info=True)
            raise
