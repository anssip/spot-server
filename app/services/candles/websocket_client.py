import asyncio
import json
import logging
import websockets
from typing import Callable
from .models import CandleMessage
from .firestore_service import FirestoreService

# Create a formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Create and configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create console handler and set level
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

# Add handler to logger if it doesn't already have handlers
if not logger.handlers:
    logger.addHandler(console_handler)

class CoinbaseWebSocketClient:
    def __init__(self):
        self.ws_url = "wss://advanced-trade-ws.coinbase.com"
        self.websocket = None
        self.firestore = FirestoreService()
        self.current_candle_timestamp = None

    async def connect(self):
        logger.info("Connecting to Coinbase WebSocket")
        self.websocket = await websockets.connect(self.ws_url)

        # Subscribe to candles
        subscribe_message = {
            "type": "subscribe",
            "product_ids": ["BTC-USD"],  # Add more pairs as needed
            "channel": "candles",
            "granularity": "ONE_MINUTE"  # You can adjust the granularity
        }
        await self.websocket.send(json.dumps(subscribe_message))

    async def listen(self):
        while True:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                logger.info("Received message")

                # Handle events array
                if 'events' in data:
                    for event in data['events']:
                        event_type = event.get('type')
                        logger.info(f"Event type: {event_type}")

                        # Process candles based on event type
                        if event_type == 'snapshot':
                            # Handle historical candles in snapshot
                            for candle in event.get('candles', []):
                                await self._process_candle(candle, store_historical=True)
                        
                        elif event_type == 'update':
                            # Handle live candle updates
                            for candle in event.get('candles', []):
                                await self._process_candle(candle, store_historical=False)

            except websockets.exceptions.ConnectionClosed:
                logger.error("Connection closed. Reconnecting...")
                await self.connect()
            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(1)

    async def _process_candle(self, candle: dict, store_historical: bool):
        """Helper method to process individual candles"""
        try:
            product_id = candle.get('product_id')
            candle_data = [
                int(candle['start']),  # timestamp
                float(candle['low']),
                float(candle['high']),
                float(candle['open']),
                float(candle['close']),
                float(candle['volume'])
            ]
            
            # Always update live candle
            await self.firestore.update_live_candle(product_id, candle_data)

            # Store historical candle only for snapshots
            if store_historical:
                await self.firestore.store_completed_candle(product_id, candle_data)
                
        except Exception as e:
            logger.error(f"Error processing candle: {e}")
