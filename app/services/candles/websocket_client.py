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
    def __init__(self):
        self.ws_url = "wss://advanced-trade-ws.coinbase.com"
        self.websocket = None
        self.firestore = FirestoreService()
        self.aggregator = CandleAggregator()
        self.connected = False
        self.should_run = True
        self.connection_attempts = 0
        self.last_message_time = None
        self.HEARTBEAT_INTERVAL = 30  # seconds
        self.MAX_MESSAGE_GAP = 60  # seconds
        self.MAX_RETRIES_BEFORE_RESTART = 10

    async def _check_connection_health(self):
        """Monitor connection health and force reconnect if needed"""
        while self.should_run:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                
                if self.last_message_time:
                    time_since_last_message = time.time() - self.last_message_time
                    if time_since_last_message > self.MAX_MESSAGE_GAP:
                        logger.warning(f"No messages received for {time_since_last_message} seconds. Forcing reconnect...")
                        self.connected = False
                        if self.websocket:
                            await self.websocket.close()
                
                if self.connection_attempts >= self.MAX_RETRIES_BEFORE_RESTART:
                    logger.error("Max connection attempts reached. Initiating full restart...")
                    self.should_run = False
                    # Optionally trigger process restart here
                    sys.exit(1)  # Process manager should restart the service
                    
            except Exception as e:
                logger.error(f"Error in health check: {e}")

    async def connect(self):
        """Connect and subscribe to WebSocket feed"""
        try:
            self.connection_attempts += 1
            logger.info(f"Connecting to Coinbase WebSocket (attempt {self.connection_attempts})")
            
            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10,
                compression=None  # Disable compression to reduce complexity
            )
            
            # Subscribe to candles
            subscribe_message = {
                "type": "subscribe",
                "product_ids": ["BTC-USD"],
                "channel": "candles",
                "granularity": "ONE_HOUR"
            }
            await self.websocket.send(json.dumps(subscribe_message))
            
            # Reset connection tracking on successful connection
            self.connected = True
            self.connection_attempts = 0
            self.last_message_time = time.time()
            logger.info("Successfully connected and subscribed")
            
        except Exception as e:
            self.connected = False
            logger.error(f"Connection error: {e}")
            raise

    async def listen(self):
        """Main listening loop with improved error handling"""
        # Start health check task
        health_check_task = asyncio.create_task(self._check_connection_health())
        
        while self.should_run:
            try:
                if not self.connected:
                    await self.connect()
                
                async with async_timeout.timeout(self.MAX_MESSAGE_GAP):
                    message = await self.websocket.recv()
                    self.last_message_time = time.time()
                    
                    data = json.loads(message)
                    logger.debug("Received message")  # Changed to debug level

                    if 'events' in data:
                        for event in data['events']:
                            event_type = event.get('type')
                            
                            if event_type == 'snapshot':
                                for candle in event.get('candles', []):
                                    await self._process_candle(candle, store_historical=True)
                            
                            elif event_type == 'update':
                                for candle in event.get('candles', []):
                                    logger.info(f"Updating candle: {candle}")
                                    await self._process_candle(candle, store_historical=False)

            except asyncio.TimeoutError:
                logger.warning("Message timeout - initiating reconnect")
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
            
            # Always update live 5-min candle
            await self.firestore.update_live_candle(f"{product_id}_5m", candle_data)

            # Get current state of hourly candle and whether it's complete
            hourly_candle, is_complete = self.aggregator.update_hourly_candle(product_id, candle_data)

            # Always update live hourly candle
            await self.firestore.update_live_candle(product_id, hourly_candle)
            
            # Store historical candle only
            if is_complete and store_historical:
                await self.firestore.store_completed_candle(product_id, hourly_candle)
                
        except Exception as e:
            logger.error(f"Error processing candle: {e}", exc_info=True)
