import asyncio
import json
import websockets
from typing import Callable
from .models import TickerMessage


class CoinbaseWebSocketClient:
    def __init__(self):
        self.ws_url = "wss://advanced-trade-ws.coinbase.com"
        self.websocket = None
        self.callbacks = []

    async def connect(self):
        self.websocket = await websockets.connect(self.ws_url)

        # Subscribe to ticker
        subscribe_message = {
            "type": "subscribe",
            "product_ids": ["BTC-USD"],  # Add more pairs as needed
            "channel": "ticker"
        }
        await self.websocket.send(json.dumps(subscribe_message))

    async def listen(self):
        while True:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)

                if data.get("type") == "ticker":
                    ticker = TickerMessage(**data)
                    # Notify all registered callbacks
                    for callback in self.callbacks:
                        await callback(ticker)

            except websockets.exceptions.ConnectionClosed:
                print("Connection closed. Reconnecting...")
                await self.connect()
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(1)

    def add_callback(self, callback: Callable):
        self.callbacks.append(callback)

    async def close(self):
        if self.websocket:
            await self.websocket.close()
