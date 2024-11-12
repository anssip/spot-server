import asyncio
import json
import websockets
from typing import Callable
from .models import CandleMessage


class CoinbaseWebSocketClient:
    def __init__(self):
        self.ws_url = "wss://advanced-trade-ws.coinbase.com"
        self.websocket = None
        self.callbacks = []

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
