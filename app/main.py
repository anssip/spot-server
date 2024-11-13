from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
import uvicorn
import signal
import sys

from app.services.candles.websocket_client import CoinbaseWebSocketClient

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store the websocket client instance
websocket_client = None

async def start_websocket_client():
    global websocket_client
    websocket_client = CoinbaseWebSocketClient()
    await websocket_client.connect()
    asyncio.create_task(websocket_client.listen())

@app.on_event("startup")
async def startup_event():
    await start_websocket_client()

@app.on_event("shutdown")
async def shutdown_event():
    if websocket_client and websocket_client.websocket:
        await websocket_client.websocket.close()

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
