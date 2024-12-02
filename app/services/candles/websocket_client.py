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
import psutil
import socket
import aiohttp

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
        self.CONNECT_TIMEOUT = 60       # Increased from 30 to 60
        self.RECONNECT_DELAY = 30       # Increased from 5 to 30
        self.MAX_RETRIES = 3           # Reduced from 10 to 3
        self.HEARTBEAT_INTERVAL = 30
        self.MAX_MESSAGE_GAP = 120
        self.MAX_BATCH_SIZE = 100
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
        
        logger.info(f"Initialized {client_id}, products: {product_ids}")

    @backoff.on_exception(
        backoff.expo,
        (websockets.exceptions.WebSocketException, asyncio.TimeoutError),
        max_tries=3,
        max_time=60
    )
    async def _try_connect(self):
        """Attempt to establish WebSocket connection with retries"""
        return await websockets.connect(
            self.uri,
            ping_interval=20,
            ping_timeout=30,
            close_timeout=20,
            compression=None,
            max_size=2**20,
            max_queue=None,
            ssl=True
        )

    async def _check_dns(self):
        """Check DNS resolution for the WebSocket host"""
        try:
            host = self.uri.split('://')[1]
            ip = socket.gethostbyname(host)
            logger.info(f"{self.client_id}: Resolved {host} to {ip}")
            return True
        except Exception as e:
            logger.error(f"{self.client_id}: DNS resolution failed: {e}")
            return False

    async def _log_network_info(self):
        """Log network diagnostic information"""
        try:
            # Check if we can reach Cloudflare DNS
            socket.create_connection(("1.1.1.1", 53), timeout=3)
            logger.info(f"{self.client_id}: Internet connectivity check passed")
            
            # Try to reach Coinbase via HTTPS with timeout and retries
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                for attempt in range(3):
                    try:
                        async with session.get('https://api.coinbase.com/v2/time', 
                                            verify_ssl=False,  # Disable SSL verification for diagnostic
                                            headers={'User-Agent': 'spot-server'}) as response:
                            if response.status == 200:
                                data = await response.json()
                                logger.info(f"{self.client_id}: Coinbase API check passed")
                                return True
                            else:
                                logger.warning(f"{self.client_id}: Coinbase API check failed with status: {response.status}")
                    except Exception as e:
                        if attempt == 2:
                            logger.warning(f"{self.client_id}: Coinbase API check failed after 3 attempts: {str(e)}")
                        await asyncio.sleep(2)  # Longer delay between retries
                        continue

        except Exception as e:
            logger.error(f"{self.client_id}: Network diagnostic failed: {str(e)}")
        return False

    async def connect(self) -> tuple[bool, str]:
        if not await self._check_dns():
            await asyncio.sleep(5)  # Wait before retry
            return False, "DNS resolution failed"

        # Skip full network check if we've tried too many times
        if self.connection_attempts < 5:
            network_ok = await self._log_network_info()
            if not network_ok:
                await asyncio.sleep(5)  # Wait before retry
                return False, "Network check failed"
        
        self.connection_attempts += 1
        logger.info(f"{self.client_id}: Connecting to Coinbase WebSocket (attempt {self.connection_attempts}), products: {self.product_ids}")
        
        try:
            async with async_timeout.timeout(30):  # Reduced timeout
                try:
                    logger.debug(f"{self.client_id}: Initiating WebSocket connection")
                    self.websocket = await websockets.connect(
                        self.uri,
                        ping_interval=20,
                        ping_timeout=30,
                        close_timeout=20,
                        compression=None,
                        max_size=2**20,
                        max_queue=None,
                        ssl=True,
                        extra_headers={
                            'User-Agent': 'spot-server'
                        }
                    )
                    logger.debug(f"{self.client_id}: WebSocket connection established")
                except Exception as conn_err:
                    logger.error(f"{self.client_id}: WebSocket connection failed: {str(conn_err)}", exc_info=True)
                    return False, f"WebSocket connection error: {str(conn_err)}"

                try:
                    logger.debug(f"{self.client_id}: Preparing subscription message")
                    subscribe_message = {
                        "type": "subscribe",
                        "product_ids": self.product_ids,
                        "channel": "candles",
                        "granularity": "ONE_HOUR"
                    }
                    
                    logger.debug(f"{self.client_id}: Sending subscription message")
                    await self.websocket.send(json.dumps(subscribe_message))
                    logger.debug(f"{self.client_id}: Subscription message sent")
                    
                    subscription_timeout = time.time() + 30
                    while time.time() < subscription_timeout:
                        logger.debug(f"{self.client_id}: Waiting for subscription response")
                        response = await self.websocket.recv()
                        message = json.loads(response)
                        logger.debug(f"{self.client_id}: Received response: {message}")

                        if message.get('channel') == 'subscriptions':
                            self.connected = True
                            self.connection_attempts = 0
                            return True, "Connected successfully"
                        elif message.get('type') == 'error':
                            error_msg = message.get('message', 'Unknown error')
                            logger.error(f"{self.client_id}: Subscription error: {error_msg}")
                            return False, f"Subscription error: {error_msg}"
                    
                    logger.error(f"{self.client_id}: Subscription timeout")
                    return False, "Subscription confirmation timeout"
                except Exception as e:
                    logger.error(f"{self.client_id}: Error during subscription: {str(e)}", exc_info=True)
                    return False, f"Subscription error: {str(e)}"

        except asyncio.TimeoutError:
            logger.error(f"{self.client_id}: Overall connection timeout, products: {self.product_ids}")
            return False, "Connection timed out"
            
        except Exception as e:
            logger.error(f"{self.client_id}: Unexpected error during connect: {str(e)}", exc_info=True)
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

            logger.info(f"{self.client_id}: Processing candle for {product_id}: {candle_data}, products: {self.product_ids}")
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
        logger.info(f"{self.client_id}: Starting listen loop, products: {self.product_ids}")
        
        while self.should_run:
            try:
                if not self.connected:
                    logger.info(f"{self.client_id}: Not connected in listen loop: Attempting to connect, products: {self.product_ids}")
                    success, status = await self.connect()
                    if not success or not self.should_run:
                        logger.warning(f"{self.client_id}: Connection failed: {status}, products: {self.product_ids}")
                        await asyncio.sleep(self.RECONNECT_DELAY)
                        continue

                async with async_timeout.timeout(self.MAX_MESSAGE_GAP):
                    logger.info(f"{self.client_id}: Waiting for message, products: {self.product_ids}")
                    message = await self.websocket.recv()
                    logger.debug(f"{self.client_id}: Message received: {message}, products: {self.product_ids}")
                    
                    if not self.should_run:
                        logger.info(f"{self.client_id}: Shutdown requested, exiting listen loop, products: {self.product_ids}")
                        break
                    
                    # Process message
                    await self._handle_message(message)

            except asyncio.CancelledError:
                logger.warning(f"{self.client_id}: Listen task cancelled, products: {self.product_ids}")
                break
                
            except asyncio.TimeoutError:
                if not self.should_run:
                    break
                logger.warning(f"{self.client_id}: Message timeout - initiating reconnect, products: {self.product_ids}")
                self.connected = False
                if self.websocket:
                    await self.websocket.close()
                continue
                
            except websockets.exceptions.ConnectionClosed:
                if not self.should_run:
                    break
                logger.warning(f"{self.client_id}: Connection closed - initiating reconnect, products: {self.product_ids}")
                self.connected = False
                continue
                
            except Exception as e:
                if not self.should_run:
                    break
                logger.error(f"{self.client_id}: Error in listen loop: {e}, products: {self.product_ids}", exc_info=True)
                self.connected = False
                await asyncio.sleep(self.RECONNECT_DELAY)

        logger.info(f"{self.client_id}: Listen loop ended, products: {self.product_ids}")

    async def _check_connection_health(self):
        """Monitor connection health with improved checks"""
        while self.should_run:
            try:
                # Monitor memory usage
                process = psutil.Process()
                memory_info = process.memory_info()
                memory_percent = process.memory_percent()
                
                if memory_percent > 80:  # If using more than 80% memory
                    logger.warning(f"{self.client_id}: High memory usage: {memory_percent}%")
                
                logger.info(f"{self.client_id}: Memory usage: {memory_info.rss / 1024 / 1024:.1f} MB ({memory_percent:.1f}%)")
                
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
            logger.info(f"{self.client_id}: Message: {message}, products: {self.product_ids}")

            message_type = message.get("type")
            channel = message.get("channel")

            logger.debug(f"{self.client_id}: Message type: {message_type}, channel: {channel}")
            
            # Handle subscription messages
            if channel == 'subscriptions':
                logger.info(f"{self.client_id}: Received subscription update")
                return
            
            # Handle candle messages
            # {'channel': 'candles', 'client_id': '', 'timestamp': '2024-12-01T14:14:35.576866765Z', 'sequence_num': 5, 'events': [{'type': 'update', 'candles': [{'start': '1733062200', 'high': '97299.99', 'low': '97199.63', 'open': '97285.3', 'close': '97199.63', 'volume': '8.25478631', 'product_id': 'BTC-USD'}]}]}

            elif channel == 'candles':
                events = message.get('events', [])
                for event in events:
                    event_type = event.get('type')
                    if event_type == 'snapshot':
                        logger.info(f"{self.client_id}: Processing candle snapshot, products: {self.product_ids}")
                        for candle in event.get('candles', []):
                            await self._process_candle(candle, store_historical=True)
                                
                    elif event_type == 'update':
                        logger.info(f"{self.client_id}: Processing candle update, products: {self.product_ids}")
                        candle = event.get('candle', {})
                        if candle:
                            await self._process_candle(candle, store_historical=False)
                        else:
                            for candle in event.get('candles', []):
                                await self._process_candle(candle, store_historical=True)
            
            # Handle error messages
            elif message_type == "error":
                error_msg = message.get("message", "Unknown error")
                logger.error(f"{self.client_id}: Received error: {error_msg}")
            
            # Handle heartbeat messages
            elif message_type == "heartbeat":
                logger.debug(f"{self.client_id}: Received heartbeat")
            
            # Log unknown messages
            else:
                logger.debug(f"{self.client_id}: Unknown message: {message}")
            
            # Update last message time
            self.last_message_time = time.time()
            
        except Exception as e:
            logger.error(f"{self.client_id}: Error handling message: {e}", exc_info=True)
