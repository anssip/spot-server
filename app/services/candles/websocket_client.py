import asyncio
import json
import logging
import websockets
from typing import Callable
import backoff
from .models import CandleMessage
from .firestore_service import FirestoreService
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
import time
import sys
import async_timeout

# Just get the logger, don't configure it
logger = logging.getLogger(__name__)

@dataclass
class CandleBuffer:
    open: float
    high: float
    low: float
    close: float
    volume: float
    first_timestamp: int
    last_timestamp: int

class CandleAggregator:
    def __init__(self):
        self.hourly_candles = defaultdict(dict)
    
    def update_hourly_candle(self, product_id: str, candle_data: List) -> tuple[List, bool]:
        """
        Takes a 5-min candle and returns:
        - The current state of the hourly candle
        - Boolean indicating if the candle is completed
        """
        timestamp, low, high, open_price, close, volume = candle_data
        
        # Calculate the start of the current hour
        hour_timestamp = timestamp - (timestamp % 3600)  # Round down to nearest hour
        key = (product_id, hour_timestamp)

        current = self.hourly_candles[key]
        
        if not current:
            # First 5-min candle for this hour
            current = CandleBuffer(
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                first_timestamp=timestamp,
                last_timestamp=timestamp
            )
        else:
            # Update existing hourly candle
            current.high = max(current.high, high)
            current.low = min(current.low, low)
            current.close = close
            current.volume += volume
            current.last_timestamp = timestamp

        self.hourly_candles[key] = current

        # Always emit the current state
        hourly_data = [
            hour_timestamp,  # Always use the hour-aligned timestamp
            current.low,
            current.high,
            current.open,
            current.close,
            current.volume
        ]

        # Check if the hour is complete (difference >= 3600 seconds)
        is_complete = (current.last_timestamp - hour_timestamp) >= 3600
        if is_complete:
            # Clean up the completed hour
            del self.hourly_candles[key]

        return hourly_data, is_complete

class CoinbaseWebSocketClient:
    def __init__(self, product_ids: List[str], client_id: str, firestore_service: FirestoreService):
        self.CONNECT_TIMEOUT = 15  # seconds
        self.RECONNECT_DELAY = 2   # seconds
        self.MAX_RETRIES = 5       # max retries per connection attempt
        self.HEARTBEAT_INTERVAL = 30  # seconds
        self.MAX_MESSAGE_GAP = 60   # seconds
        self.uri = "wss://advanced-trade-ws.coinbase.com"
        self.websocket = None
        self.firestore = firestore_service
        self.aggregator = CandleAggregator()
        self.connected = False
        self.should_run = True
        self.connection_attempts = 0
        self.last_message_time = None
        self.product_ids = product_ids
        self.client_id = client_id
        self._health_check_task = None
        self._listen_task = None
        
        logger.info(f"Initialized {client_id} for products: {product_ids}")

    async def connect(self) -> bool:
        """Connect to the WebSocket with improved error handling"""
        self.connection_attempts += 1
        logger.info(f"{self.client_id}: Connecting to Coinbase WebSocket (attempt {self.connection_attempts})")
        
        try:
            # Use connect with explicit timeout
            async with async_timeout.timeout(self.CONNECT_TIMEOUT):
                self.websocket = await websockets.connect(
                    self.uri,
                    ping_interval=20,
                    ping_timeout=30,
                    close_timeout=20,
                )

            # Send subscription message
            subscribe_message = {
                "type": "subscribe",
                "product_ids": self.product_ids,
                "channel": "candles",
                "granularity": "ONE_HOUR"
            }
            
            async with async_timeout.timeout(5):
                await self.websocket.send(json.dumps(subscribe_message))
                
                # Wait for subscription confirmation
                while True:
                    response = await self.websocket.recv()
                    result = await self._handle_message(response, during_connect=True)
                    if result == "subscribed":
                        break
                    
                    if time.time() - self.last_message_time > self.CONNECT_TIMEOUT:
                        raise Exception("Subscription confirmation timeout")

            self.connected = True
            logger.info(f"{self.client_id}: Successfully connected and subscribed to {len(self.product_ids)} products")
            
            # Reset connection attempts on successful connection
            self.connection_attempts = 0
            
            # Start health check if not already running
            if not self._health_check_task or self._health_check_task.done():
                self._health_check_task = asyncio.create_task(self._check_connection_health())
            
            return True

        except asyncio.TimeoutError:
            logger.error(f"{self.client_id}: Connection timed out")
            self.connected = False
            return False
            
        except Exception as e:
            logger.error(f"{self.client_id}: Connection error: {e}")
            self.connected = False
            return False

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
            
            # Store live candle under exchanges/coinbase/products/product_id structure
            await self.firestore.update_live_candle(f"exchanges/coinbase/products/{product_id}", candle_data)

            # Update hourly aggregation
            hourly_candle, _ = self.aggregator.update_hourly_candle(product_id, candle_data)
            await self.firestore.update_live_candle(f"exchanges/coinbase/products/{product_id}/intervals/1h", hourly_candle)

            # TODO: Update other interval aggregations also
                
        except Exception as e:
            logger.error(f"Error processing candle: {e}", exc_info=True)

    async def listen(self):
        """Main listening loop with improved error handling"""
        while self.should_run:
            try:
                if not self.connected:
                    success = await self.connect()
                    if not success or not self.should_run:  # Check shutdown flag
                        await asyncio.sleep(self.RECONNECT_DELAY)
                        continue

                async with async_timeout.timeout(self.MAX_MESSAGE_GAP):
                    message = await self.websocket.recv()
                    if not self.should_run:  # Check shutdown flag
                        break
                    
                    # Process message
                    await self._handle_message(message)

            except asyncio.CancelledError:
                logger.info(f"{self.client_id}: Listen task cancelled")
                break
                
            except asyncio.TimeoutError:
                if not self.should_run:  # Check shutdown flag
                    break
                logger.warning(f"{self.client_id}: Message timeout - initiating reconnect")
                self.connected = False
                if self.websocket:
                    await self.websocket.close()
                continue
                
            except websockets.exceptions.ConnectionClosed:
                if not self.should_run:  # Check shutdown flag
                    break
                logger.warning(f"{self.client_id}: Connection closed - initiating reconnect")
                self.connected = False
                continue
                
            except Exception as e:
                if not self.should_run:  # Check shutdown flag
                    break
                logger.error(f"{self.client_id}: Error in listen loop: {e}")
                self.connected = False
                await asyncio.sleep(self.RECONNECT_DELAY)

        logger.info(f"{self.client_id}: Listen loop ended")

    async def _check_connection_health(self):
        """Monitor connection health with improved checks"""
        while self.should_run:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                
                if not self.should_run:
                    break
                    
                if self.last_message_time:
                    time_since_last_message = time.time() - self.last_message_time
                    if time_since_last_message > self.MAX_MESSAGE_GAP:
                        logger.warning(f"{self.client_id}: No messages received for {time_since_last_message} seconds")
                        self.connected = False
                        if self.websocket:
                            await self.websocket.close()
                
            except Exception as e:
                logger.error(f"{self.client_id}: Error in health check: {e}")

    async def disconnect(self):
        """Gracefully disconnect the websocket connection"""
        logger.info(f"{self.client_id}: Disconnecting websocket client")
        self.should_run = False
        
        try:
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
                
            if hasattr(self, 'websocket') and self.websocket:
                await self.websocket.close()
                
            self.connected = False
            logger.info(f"{self.client_id}: Websocket client disconnected")
            
        except Exception as e:
            logger.error(f"{self.client_id}: Error disconnecting websocket: {e}")

    async def _handle_message(self, raw_message: str, during_connect: bool = False):
        """Process incoming WebSocket messages
        
        Args:
            raw_message: The raw message from websocket
            during_connect: Whether this is during connection phase
        """
        try:
            message = json.loads(raw_message)
            message_type = message.get("type")

            print(f"Message type: {message_type}, channel: {message.get('channel')}")
            
            # First check if it's a candles message regardless of type
            if message.get('channel') == 'candles':
                events = message.get('events', [])
                for event in events:
                    event_type = event.get('type')
                    print(f"Event type: {event_type}")
                    if event_type == 'snapshot':
                        log_level = logging.INFO if during_connect else logging.DEBUG
                        logger.log(log_level, f"{self.client_id}: Processing candle snapshot")
                        # Process each candle in the snapshot
                        for candle in event.get('candles', []):
                            try:
                                await self._process_candle(candle, store_historical=True)
                            except Exception as e:
                                logger.error(f"{self.client_id}: Error processing snapshot candle: {e}")
                                if during_connect:
                                    raise
                                
                    elif event_type == 'update':
                        # Process the update candle
                        try:
                            candle = event.get('candle', {})
                            if not candle:  # Skip empty updates silently
                                continue
                            await self._process_candle(candle, store_historical=False)
                        except Exception as e:
                            logger.error(f"{self.client_id}: Error processing update candle: {e}")
                            if during_connect:
                                raise
            
            # Then check message type
            elif message_type == "error":
                error_msg = message.get("message", "Unknown error")
                logger.error(f"{self.client_id}: Received error from Coinbase: {error_msg}")
                raise Exception(f"WebSocket error: {error_msg}")
                
            elif message_type == "subscriptions":
                if during_connect:
                    # Verify the subscribed products match what we requested
                    subscribed_products = []
                    for channel in message.get('events', [{}])[0].get('subscriptions', {}).get('candles', []):
                        subscribed_products.append(channel)
                    
                    if not all(product in subscribed_products for product in self.product_ids):
                        missing = set(self.product_ids) - set(subscribed_products)
                        raise Exception(f"Not all products were subscribed. Missing: {missing}")
                    return "subscribed"
                            
            elif message_type == "heartbeat":
                logger.debug(f"{self.client_id}: Received heartbeat")
                
            else:
                # Only log unknown message types if they're not None and not candles
                if message_type is not None or message.get('channel') != 'candles':
                    logger.warning(f"{self.client_id}: Received unknown message type: {message_type}")
            
            # Update last message time for health check
            self.last_message_time = time.time()
            
        except Exception as e:
            if during_connect:
                raise
            logger.error(f"{self.client_id}: Error handling message: {e}", exc_info=True)
