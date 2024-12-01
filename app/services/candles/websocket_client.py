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
        self.ws_url = "wss://advanced-trade-ws.coinbase.com"
        self.websocket = None
        self.firestore = firestore_service
        self.aggregator = CandleAggregator()
        self.connected = False
        self.should_run = True
        self.connection_attempts = 0
        self.last_message_time = None
        self.HEARTBEAT_INTERVAL = 30  # Check every 30 seconds instead of 1 hour
        self.MAX_MESSAGE_GAP = 120    # Allow 2 minutes before forcing reconnect
        self.MAX_RETRIES_BEFORE_RESTART = 20  # Allow more retries
        self.product_ids = product_ids
        self.client_id = client_id
        self._health_check_task = None
        self._listen_task = None
        
        logger.info(f"Initialized {client_id} for products: {product_ids}")

    async def connect(self):
        """Connect and subscribe to WebSocket feed"""
        try:
            self.connection_attempts += 1
            logger.info(f"{self.client_id}: Connecting to Coinbase WebSocket (attempt {self.connection_attempts})")
            
            # Increase connection timeout
            async with async_timeout.timeout(60):  # Increased from 30
                self.websocket = await websockets.connect(
                    self.ws_url,
                    ping_interval=20,
                    ping_timeout=30,    # Increased from 20
                    close_timeout=20,   # Increased from 10
                    compression=None,
                    max_size=None
                )
            
            subscribe_message = {
                "type": "subscribe",
                "product_ids": self.product_ids,
                "channel": "candles",
                "granularity": "ONE_HOUR"
            }
            
            # Use a timeout for the subscription and message processing
            async with async_timeout.timeout(30):
                await self.websocket.send(json.dumps(subscribe_message))
                
                # Process initial messages and wait for subscription confirmation
                subscription_confirmed = False
                snapshot_count = 0
                expected_snapshots = len(self.product_ids)
                
                while not subscription_confirmed or snapshot_count < expected_snapshots:
                    response = await self.websocket.recv()
                    data = json.loads(response)
                    logger.debug(f"{self.client_id}: Processing response: {data.get('type', 'unknown')}")
                    
                    if data.get('type') == 'error':
                        raise Exception(f"Subscription error: {data.get('message')}")
                    
                    elif data.get('channel') == 'subscriptions':
                        subscribed_products = []
                        for channel in data.get('events', [{}])[0].get('subscriptions', {}).get('candles', []):
                            subscribed_products.append(channel)
                        
                        if all(product in subscribed_products for product in self.product_ids):
                            logger.info(f"{self.client_id}: Subscription confirmed for all products")
                            subscription_confirmed = True
                        else:
                            missing = set(self.product_ids) - set(subscribed_products)
                            raise Exception(f"Not all products were subscribed. Missing: {missing}")
                    
                    elif data.get('events', [{}])[0].get('type') == 'snapshot':
                        snapshot_count += 1
                        logger.debug(f"{self.client_id}: Received snapshot {snapshot_count}/{expected_snapshots}")
            
            self.connected = True
            self.connection_attempts = 0
            self.last_message_time = time.time()
            logger.info(f"{self.client_id}: Successfully connected and subscribed to {len(self.product_ids)} products")
            
        except asyncio.TimeoutError:
            self.connected = False
            raise Exception(f"{self.client_id}: Connection/subscription timed out")
            
        except Exception as e:
            self.connected = False
            logger.error(f"{self.client_id}: Connection error: {str(e)}")
            raise

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
        try:
            self._health_check_task = asyncio.create_task(self._check_connection_health())
            message_count = 0
            last_log_time = time.time()
            
            while self.should_run:
                try:
                    if not self.connected:
                        await self.connect()
                    
                    # Add timeout for websocket receive
                    async with async_timeout.timeout(self.MAX_MESSAGE_GAP):
                        message = await self.websocket.recv()
                        
                        # Check should_run again after await
                        if not self.should_run:
                            break
                            
                        self.last_message_time = time.time()
                        message_count += 1
                        
                        # Log message rates every minute
                        current_time = time.time()
                        if current_time - last_log_time >= 60:
                            logger.info(f"{self.client_id}: Received {message_count} messages in last minute")
                            message_count = 0
                            last_log_time = current_time
                        
                        data = json.loads(message)
                        
                        if 'events' in data:
                            for event in data['events']:
                                event_type = event.get('type')
                                candles = event.get('candles', [])
                                
                                if event_type in ['snapshot', 'update']:
                                    logger.debug(f"{self.client_id}: Received {event_type} with {len(candles)} candles")
                                    for candle in candles:
                                        await self._process_candle(candle, store_historical=False)
                        else:
                            logger.debug(f"{self.client_id}: Received message without events: {data}")

                except asyncio.CancelledError:
                    logger.info(f"{self.client_id}: Listen task cancelled")
                    break
                    
                except asyncio.TimeoutError:
                    if not self.should_run:
                        break
                    logger.warning(f"{self.client_id}: Message timeout - initiating reconnect")
                    self.connected = False
                    continue
                    
                except (websockets.exceptions.ConnectionClosed, 
                        websockets.exceptions.WebSocketException) as e:
                    logger.error(f"WebSocket error: {e}")
                    self.connected = False
                    await asyncio.sleep(1)
                    continue
                    
                except Exception as e:
                    logger.error(f"Unexpected error: {e}", exc_info=True)
                    await asyncio.sleep(1)
                    continue

        finally:
            # Cleanup when the listen loop exits
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
            await self.disconnect()

    async def _check_connection_health(self):
        """Monitor connection health and force reconnect if needed"""
        try:
            while self.should_run:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                
                if not self.should_run:
                    break
                    
                if self.last_message_time:
                    time_since_last_message = time.time() - self.last_message_time
                    if time_since_last_message > self.MAX_MESSAGE_GAP:
                        logger.warning(f"No messages received for {time_since_last_message} seconds. Forcing reconnect...")
                        self.connected = False
                        if self.websocket:
                            await self.websocket.close()
                
                if self.connection_attempts >= self.MAX_RETRIES_BEFORE_RESTART:
                    logger.error(f"Max connection attempts ({self.MAX_RETRIES_BEFORE_RESTART}) reached. Initiating full restart...")
                    self.should_run = False
                    sys.exit(1)  # Process manager should restart the service
                    
        except asyncio.CancelledError:
            logger.info(f"{self.client_id}: Health check task cancelled")
            
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
