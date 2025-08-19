import asyncio
import json
import logging
import websockets
from typing import Callable
from .firestore_service import FirestoreService
from .models import Candle, Granularity
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple
import time
import async_timeout

# Just get the logger, don't configure it
logger = logging.getLogger(__name__)

class CandleAggregator:
    def __init__(self):
        # Map of (product_id, interval, timestamp) -> CandleBuffer
        self.candles: Dict[Tuple[str, Granularity, int], Candle] = {}
    
    def _get_interval_timestamp(self, timestamp: int, granularity: Granularity) -> int:
        """Get the start timestamp for an interval"""
        return timestamp - (timestamp % granularity.seconds)

    def update_candle(self, product_id: str, candle: Candle) -> List[Tuple[Granularity, Candle, bool]]:
        """Updates candles for all granularities"""
        updates = []

        for granularity in Granularity:
            interval_timestamp = self._get_interval_timestamp(candle.first_timestamp, granularity)
            key = (product_id, granularity, interval_timestamp)
            
            current = self.candles.get(key)
            if not current:
                # First candle for this interval
                current = Candle(
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                    first_timestamp=candle.first_timestamp,
                    last_timestamp=candle.last_timestamp
                )
            else:
                # Update existing candle
                current.high = max(current.high, candle.high)
                current.low = min(current.low, candle.low)
                current.close = candle.close
                current.volume += candle.volume
                current.last_timestamp = candle.last_timestamp

            self.candles[key] = current

            # Check if interval is complete
            is_complete = (candle.last_timestamp - interval_timestamp) >= granularity.seconds
            if is_complete:
                del self.candles[key]

            updates.append((granularity, current, is_complete))

        return updates

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


    async def connect(self) -> tuple[bool, str]:        
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
                        elif message.get('type') != 'error':
                            logger.warning(f"{self.client_id}: Unknown message: {message.get('type')}/{message.get('channel')}, assuming were connected")
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
            candle_buffer = Candle.from_coinbase_message(candle)

            # Update all intervals
            updates = self.aggregator.update_candle(product_id, candle_buffer)
            
            for granularity, interval_data, is_complete in updates:
                await self.firestore.update_live_candle(
                    f"exchanges/coinbase/products/{product_id}/intervals/{granularity.value}",
                    interval_data.to_list()
                )
                # TODO: Send pubsub message if we have active subscribers. This will trigger cancle functions.
                
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
                    if not success:
                        logger.warning(f"{self.client_id}: Connection failed: {status}, products: {self.product_ids}")
                        await self._close_websocket()

                        delay = min(30, self.RECONNECT_DELAY * (2 ** (self.connection_attempts - 1)))
                        logger.info(f"{self.client_id}: Waiting {delay}s before reconnect attempt")
                        await asyncio.sleep(delay)
                        
                        continue
                    else:
                        logger.info(f"{self.client_id}: Connected successfully! Products: {self.product_ids}")

                async with async_timeout.timeout(self.MAX_MESSAGE_GAP):
                    message = await self.websocket.recv()
                    
                    if not self.should_run:
                        break
                    
                    # Process message
                    await self._handle_message(message)

            except asyncio.CancelledError:
                logger.warning(f"{self.client_id}: Listen task cancelled, products: {self.product_ids}")
                await self._close_websocket()
                await asyncio.sleep(self.RECONNECT_DELAY)
                continue
                
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed) as e:
                if not self.should_run:
                    break
                logger.warning(f"{self.client_id}: Connection error ({type(e).__name__}), initiating reconnect")
                await self._close_websocket()
                await asyncio.sleep(self.RECONNECT_DELAY)
                continue
                
            except Exception as e:
                if not self.should_run:
                    break
                logger.error(f"{self.client_id}: Error in listen loop: {e}", exc_info=True)
                await self._close_websocket()
                await asyncio.sleep(self.RECONNECT_DELAY)

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
                
            await self._close_websocket()
            logger.info(f"{self.client_id}: Websocket client disconnected")
            
        except Exception as e:
            logger.error(f"{self.client_id}: Error disconnecting websocket: {e}")

    async def _handle_message(self, raw_message: str):
        """Process incoming WebSocket messages"""
        try:
            message = json.loads(raw_message)
            logger.debug(f"{self.client_id}: Message: {message}, products: {self.product_ids}")

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
                    # if event_type == 'snapshot':
                    #     logger.info(f"{self.client_id}: Processing candle snapshot, products: {self.product_ids}")
                    #     for candle in event.get('candles', []):
                    #         await self._process_candle(candle, store_historical=True)
                                
                    if event_type == 'update':
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

    async def _close_websocket(self):
        """Helper to safely close websocket"""
        if self.websocket and not self.websocket.closed:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.warning(f"{self.client_id}: Error closing websocket: {e}")
        self.websocket = None
        self.connected = False
