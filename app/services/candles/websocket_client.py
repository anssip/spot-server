import asyncio
import json
import logging
import websockets
from typing import Callable
import backoff
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
        self.reconnect_delay = 1  # Start with 1 second delay
        self.max_reconnect_delay = 60  # Maximum delay of 60 seconds
        self.connected = False

    @backoff.on_exception(
        backoff.expo,
        (websockets.exceptions.WebSocketException, TimeoutError),
        max_tries=None,  # Keep trying indefinitely
        max_time=300,    # Maximum total time for retries
        on_backoff=lambda details: logger.info(f"Backing off {details['wait']} seconds after {details['tries']} tries")
    )
    async def connect(self):
        try:
            logger.info("Connecting to Coinbase WebSocket")
            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10
            )
            
            # Subscribe to candles
            # TODO: handle granularity
            subscribe_message = {
                "type": "subscribe",
                "product_ids": ["BTC-USD"],
                "channel": "candles",
                "granularity": "ONE_HOUR"
            }
            await self.websocket.send(json.dumps(subscribe_message))
            self.connected = True
            logger.info("Successfully connected and subscribed")
            
        except Exception as e:
            self.connected = False
            logger.error(f"Connection error: {e}")
            raise  # Re-raise for backoff to handle

    async def listen(self):
        while True:
            try:
                if not self.connected:
                    await self.connect()
                
                message = await self.websocket.recv()
                data = json.loads(message)
                logger.info("Received message")

                if 'events' in data:
                    for event in data['events']:
                        event_type = event.get('type')
                        logger.info(f"Event type: {event_type}")

                        if event_type == 'snapshot':
                            for candle in event.get('candles', []):
                                await self._process_candle(candle, store_historical=True)
                        
                        elif event_type == 'update':
                            for candle in event.get('candles', []):
                                logger.info(f"Updating candle: {candle}")
                                await self._process_candle(candle, store_historical=False)

            except (websockets.exceptions.ConnectionClosed, TimeoutError) as e:
                self.connected = False
                logger.error(f"Connection error: {e}")
                await asyncio.sleep(1)  # Brief pause before reconnect attempt
                continue
                
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                await asyncio.sleep(1)
                continue

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
