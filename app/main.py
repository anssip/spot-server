from typing import List
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
import uvicorn
import signal
import sys
import logging
import async_timeout
from contextlib import asynccontextmanager

from app.services.candles.firestore_service import FirestoreService
from app.services.candles.websocket_client import CoinbaseWebSocketClient

# Configure logging at the application level
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

logging.getLogger('app.services.candles.firestore_service').setLevel(logging.INFO)
logging.getLogger('app.services.candles.websocket_client').setLevel(logging.INFO)
logging.getLogger('app.main').setLevel(logging.INFO)

# Reduce noise from other modules
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('google').setLevel(logging.WARNING)

shutdown_event = asyncio.Event()
websocket_clients = None
firestore_service = None
startup_complete = asyncio.Event()
app_ready = asyncio.Event()

def signal_handler(sig, frame):
    logger.info(f"Received signal {sig}, initiating shutdown...")
    if not shutdown_event.is_set():
        shutdown_event.set()
        # Force exit if we haven't completed startup
        if not startup_complete.is_set():
            logger.info("Forcing exit during startup phase")
            sys.exit(1)

# Module-level initialization
app = FastAPI()
startup_complete = asyncio.Event()
app_ready = asyncio.Event()
websocket_clients = None
firestore_service = None

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    # Always respond during startup, just indicate we're not ready yet
    if not startup_complete.is_set():
        return {
            "status": "starting",
            "message": "Application is initializing",
            "websocket_clients": len(websocket_clients) if websocket_clients else 0
        }, 200  # Return 200 during startup so Cloud Run doesn't kill the container

    # After startup, perform full health check
    if not app_ready.is_set():
        return {"status": "degraded", "reason": "initialization_incomplete"}, 503

    if not websocket_clients:
        return {"status": "unhealthy", "reason": "no_websocket_clients"}, 503

    connected_clients = sum(1 for client in websocket_clients if client.connected)
    total_clients = len(websocket_clients)

    if connected_clients < total_clients:
        return {
            "status": "degraded",
            "connected": connected_clients,
            "total": total_clients
        }, 503

    return {
        "status": "healthy",
        "connected_clients": connected_clients,
        "total_clients": total_clients
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI application"""
    try:
        # Start WebSocket client initialization in a background task
        init_task = asyncio.create_task(initialize_websocket_clients())
        startup_complete.set()  # Mark that we've started initialization
        
        logger.info("Application startup initiated, beginning WebSocket client initialization")
        yield
        
    finally:
        logger.info("Shutting down application...")
        if websocket_clients:
            shutdown_tasks = []
            for client in websocket_clients:
                client.should_run = False
                shutdown_tasks.append(client.disconnect())
            
            try:
                async with async_timeout.timeout(30):
                    await asyncio.gather(*shutdown_tasks)
            except asyncio.TimeoutError:
                logger.warning("Shutdown timed out while waiting for websocket clients")
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
        
        startup_complete.clear()
        app_ready.clear()
        logger.info("Shutdown complete")

async def initialize_websocket_clients():
    """Initialize WebSocket clients in the background"""
    global websocket_clients
    try:
        websocket_clients = await start_websocket_clients()
        if websocket_clients:
            app_ready.set()
            logger.info(f"WebSocket client initialization complete with {len(websocket_clients)} clients")
        else:
            logger.error("Failed to initialize WebSocket clients")
    except Exception as e:
        logger.error(f"Error initializing WebSocket clients: {e}")
        # Don't re-raise the exception - let the application continue running

# Add lifespan to FastAPI app
app.router.lifespan_context = lifespan

def partition_products(products: List[str], size: int = 5) -> List[List[str]]:
    """Split products into smaller groups for better performance"""
    return [products[i:i + size] for i in range(0, len(products), size)]

async def start_websocket_clients():
    try:
        global firestore_service, websocket_clients
        firestore_service = FirestoreService()
        
        if shutdown_event.is_set():
            logger.info("Shutdown signal received during startup, aborting client creation")
            return []
            
        products = await firestore_service.get_products('coinbase', 'online')
        product_ids = [p.source for p in products]
        
        logger.debug(f"Found {len(product_ids)} active products")
        
        if not product_ids:
            logger.error("No active products found!")
            return []
            
        product_groups = partition_products(product_ids, size=4)
        logger.debug(f"Created {len(product_groups)} websocket groups")
        
        websocket_clients = []
        
        for i, product_group in enumerate(product_groups):
            if shutdown_event.is_set():
                logger.info("Shutdown signal received, stopping client creation")
                break
                
            logger.debug(f"Creating client {i} for group: {product_group}")
            
            for attempt in range(3):
                try:
                    client = CoinbaseWebSocketClient(
                        product_group, 
                        f"ws_client_{i}", 
                        firestore_service
                    )
                    
                    async with async_timeout.timeout(45):
                        await client.connect()
                        
                    websocket_clients.append(client)
                    asyncio.create_task(client.listen())
                    logger.debug(f"Started websocket client {i} for products: {product_group}")
                    
                    await asyncio.sleep(2)
                    break
                    
                except Exception as e:
                    if shutdown_event.is_set():
                        logger.info("Shutdown signal received during retry, aborting")
                        return websocket_clients
                    logger.error(f"Error creating client {i} (attempt {attempt + 1}): {e}")
                    if attempt == 2:
                        logger.error(f"Failed to create client {i} after 3 attempts")
                    else:
                        await asyncio.sleep(5)
        
        logger.info(f"Successfully created {len(websocket_clients)} websocket clients")
        return websocket_clients
            
    except Exception as e:
        logger.error(f"Error starting websocket clients: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        timeout_keep_alive=30,
        timeout_graceful_shutdown=30,
        loop="auto",
        workers=1,
        limit_concurrency=100,
        limit_max_requests=0,
        reload=False,
        access_log=False
    )
