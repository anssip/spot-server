import asyncio
import json
import websockets
from typing import Callable
from .models import CandleMessage
from .firestore_service import FirestoreService


class CoinbaseWebSocketClient:
    def __init__(self):
        self.ws_url = "wss://advanced-trade-ws.coinbase.com"
        self.websocket = None
        self.firestore = FirestoreService()
        self.current_candle_timestamp = None

    async def connect(self):
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

                if data.get("type") == "candle":
                    product_id = data.get("product_id")
                    candle = data.get("candle")

                    # Update live candle
                    await self.firestore.update_live_candle(product_id, candle)

                    # Check if this is a new candle
                    if self.current_candle_timestamp and candle[0] > self.current_candle_timestamp:
                        # Store the previous candle as completed
                        await self.firestore.store_completed_candle(product_id, candle)

                    self.current_candle_timestamp = candle[0]

            except websockets.exceptions.ConnectionClosed:
                print("Connection closed. Reconnecting...")
                await self.connect()
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(1)
