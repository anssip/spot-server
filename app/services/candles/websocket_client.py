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

    async def connect(self) -> tuple[bool, str]:
        """Connect to the WebSocket with improved error handling"""
        self.connection_attempts += 1
        logger.info(f"{self.client_id}/{self.product_ids}: Connecting to Coinbase WebSocket (attempt {self.connection_attempts})")
        
        try:
            async with async_timeout.timeout(45):
                try:
                    self.websocket = await websockets.connect(
                        self.uri,
                        ping_interval=20,
                        ping_timeout=30,
                        close_timeout=20,
                    )
                except Exception as conn_err:
                    return False, f"WebSocket connection error: {str(conn_err)}"

                # Update subscription message with ONE_MINUTE granularity
                subscribe_message = {
                    "type": "subscribe",
                    "product_ids": self.product_ids,
                    "channel": "candles",
                    "granularity": "ONE_MINUTE"  # Changed from ONE_HOUR to get more frequent updates
                }
                
                logger.info(f"{self.client_id}/{self.product_ids}: Sending subscription: {subscribe_message}")
                await self.websocket.send(json.dumps(subscribe_message))
                
                subscription_timeout = time.time() + 30
                while time.time() < subscription_timeout:
                    response = await self.websocket.recv()
                    message = json.loads(response)
                    logger.debug(f"{self.client_id}/{self.product_ids}: Message received in connect: {message}")

                    if message.get('channel') == 'subscriptions':
                        self.connected = True
                        self.connection_attempts = 0
                        logger.info(f"{self.client_id}/{self.product_ids}: Successfully connected and subscribed")
                        return True, "Connected successfully"
                    elif message.get('type') == 'error':
                        error_msg = message.get('message', 'Unknown error')
                        return False, f"Subscription error: {error_msg}"
                        
                return False, "Subscription confirmation timeout"

        except asyncio.TimeoutError:
            return False, "Connection timed out"
            
        except Exception as e:
            return False, f"Connection error: {str(e)}"

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

            logger.info(f"{self.client_id}/{self.product_ids}: Processing candle for {product_id}: {candle_data}")
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
        logger.info(f"{self.client_id}/{self.product_ids}: Starting listen loop")
        
        while self.should_run:
            try:
                if not self.connected:
                    logger.info(f"{self.client_id}/{self.product_ids}: Not connected in listen loop: Attempting to connect")
                    success, status = await self.connect()
                    if not success or not self.should_run:
                        logger.warning(f"{self.client_id}/{self.product_ids}: Connection failed: {status}")
                        await asyncio.sleep(self.RECONNECT_DELAY)
                        continue

                async with async_timeout.timeout(self.MAX_MESSAGE_GAP):
                    logger.info(f"{self.client_id}/{self.product_ids}: Waiting for message")
                    message = await self.websocket.recv()
                    logger.debug(f"{self.client_id}/{self.product_ids}: Message received: {message}")
                    
                    if not self.should_run:
                        logger.info(f"{self.client_id}/{self.product_ids}: Shutdown requested, exiting listen loop")
                        break
                    
                    # Process message
                    await self._handle_message(message)

            except asyncio.CancelledError:
                logger.info(f"{self.client_id}/{self.product_ids}: Listen task cancelled")
                break
                
            except asyncio.TimeoutError:
                if not self.should_run:
                    break
                logger.warning(f"{self.client_id}/{self.product_ids}: Message timeout - initiating reconnect")
                self.connected = False
                if self.websocket:
                    await self.websocket.close()
                continue
                
            except websockets.exceptions.ConnectionClosed:
                if not self.should_run:
                    break
                logger.warning(f"{self.client_id}/{self.product_ids}: Connection closed - initiating reconnect")
                self.connected = False
                continue
                
            except Exception as e:
                if not self.should_run:
                    break
                logger.error(f"{self.client_id}/{self.product_ids}: Error in listen loop: {e}", exc_info=True)
                self.connected = False
                await asyncio.sleep(self.RECONNECT_DELAY)

        logger.info(f"{self.client_id}/{self.product_ids}: Listen loop ended")

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

    async def _handle_message(self, raw_message: str):
        """Process incoming WebSocket messages"""
        try:
            message = json.loads(raw_message)
            logger.info(f"{self.client_id}/{self.product_ids}: Message: {message}")

            message_type = message.get("type")
            channel = message.get("channel")

            logger.debug(f"{self.client_id}/{self.product_ids}: Message type: {message_type}, channel: {channel}")
            
            # Handle subscription messages
            if channel == 'subscriptions':
                logger.info(f"{self.client_id}/{self.product_ids}: Received subscription update")
                return
            
            # Handle candle messages
            # {'channel': 'candles', 'client_id': '', 'timestamp': '2024-12-01T14:14:35.576866765Z', 'sequence_num': 5, 'events': [{'type': 'update', 'candles': [{'start': '1733062200', 'high': '97299.99', 'low': '97199.63', 'open': '97285.3', 'close': '97199.63', 'volume': '8.25478631', 'product_id': 'BTC-USD'}]}]}

            elif channel == 'candles':
                events = message.get('events', [])
                for event in events:
                    event_type = event.get('type')
                    if event_type == 'snapshot':
                        logger.info(f"{self.client_id}/{self.product_ids}: Processing candle snapshot")
                        for candle in event.get('candles', []):
                            await self._process_candle(candle, store_historical=True)
                                
                    elif event_type == 'update':
                        logger.info(f"{self.client_id}/{self.product_ids}: Processing candle update")
                        candle = event.get('candle', {})
                        if candle:
                            await self._process_candle(candle, store_historical=False)
                        else:
                            for candle in event.get('candles', []):
                                await self._process_candle(candle, store_historical=True)
            
            # Handle error messages
            elif message_type == "error":
                error_msg = message.get("message", "Unknown error")
                logger.error(f"{self.client_id}/{self.product_ids}: Received error: {error_msg}")
            
            # Handle heartbeat messages
            elif message_type == "heartbeat":
                logger.debug(f"{self.client_id}/{self.product_ids}: Received heartbeat")
            
            # Log unknown messages
            else:
                logger.debug(f"{self.client_id}/{self.product_ids}: Unknown message: {message}")
            
            # Update last message time
            self.last_message_time = time.time()
            
        except Exception as e:
            logger.error(f"{self.client_id}/{self.product_ids}: Error handling message: {e}", exc_info=True)
