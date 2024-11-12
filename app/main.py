from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from app.services.candles.websocket_client import CoinbaseWebSocketClient

app = FastAPI()


async def start_websocket_client():
    client = CoinbaseWebSocketClient()
    await client.connect()
    asyncio.create_task(client.listen())


@app.on_event("startup")
async def startup_event():
    await start_websocket_client()

