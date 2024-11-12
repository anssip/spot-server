from fastapi import WebSocket
from .websocket_client import CoinbaseWebSocketClient


class TickerManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.client = CoinbaseWebSocketClient()
        self.client.add_callback(self.broadcast_ticker)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast_ticker(self, ticker):
        # Broadcast ticker to all connected clients
        for connection in self.active_connections:
            try:
                await connection.send_json(ticker.dict())
            except:
                await self.disconnect(connection)

    async def start(self):
        await self.client.connect()
        await self.client.listen()
