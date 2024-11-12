from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from services.ticker.manager import TickerManager
import asyncio

app = FastAPI()

# Initialize the ticker manager
ticker_manager = TickerManager()

# Start the WebSocket client in the background


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(ticker_manager.start())

# WebSocket endpoint for clients to connect for testing only
# Real clients should connect to Firestore directly as we store the ticker data in Firestore


@app.websocket("/ws/ticker")
async def websocket_endpoint(websocket: WebSocket):
    await ticker_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive
            await websocket.receive_text()
    except:
        ticker_manager.disconnect(websocket)
