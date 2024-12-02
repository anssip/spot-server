from typing import List, Optional
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
    """Handle shutdown signals"""
    logger.info(f"Received signal {sig}, initiating shutdown...")
    
    # Just disconnect all clients immediately
    if websocket_clients:
        for client in websocket_clients:
            client.should_run = False
            if client.websocket:
                loop = asyncio.get_event_loop()
                loop.create_task(client.websocket.close())
    
    # Exit after a short delay
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

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
        init_task = asyncio.create_task(initialize_websocket_clients())
        startup_complete.set()
        logger.info("Application startup initiated")
        yield
        
    finally:
        logger.info("Shutting down application...")
        if websocket_clients:
            for client in websocket_clients:
                client.should_run = False
                if client.websocket:
                    await client.websocket.close()
        
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

# Add lifespan to FastAPI app
app.router.lifespan_context = lifespan

def partition_products(products: List[str], size: int = 5) -> List[List[str]]:
    """Split products into smaller groups for better performance"""
    return [products[i:i + size] for i in range(0, len(products), size)]

# Add environment variable for shard configuration
SHARD_COUNT = int(os.getenv('SHARD_COUNT', '10'))  # Total number of shards
SHARD_INDEX = int(os.getenv('SHARD_INDEX', '0'))   # Which shard this container is

async def start_websocket_clients():
    try:
        global firestore_service, websocket_clients
        firestore_service = FirestoreService()
        
        products = await firestore_service.get_products('coinbase', 'online')
        product_ids = [p.source for p in products]
        
        # Shard the products
        products_per_shard = len(product_ids) // SHARD_COUNT
        start_idx = SHARD_INDEX * products_per_shard
        end_idx = start_idx + products_per_shard if SHARD_INDEX < SHARD_COUNT - 1 else len(product_ids)
        
        # Get this shard's products
        shard_products = product_ids[start_idx:end_idx]
        # push 'BTC-USD' to the front of the list
        # shard_products.insert(0, 'BTC-USD')
        logger.info(f"Shard {SHARD_INDEX}/{SHARD_COUNT} handling {len(shard_products)} products: {shard_products}")
        
        if shutdown_event.is_set():
            logger.info("Shutdown signal received during startup, aborting client creation")
            return []
            
        logger.debug(f"Found {len(shard_products)} active products")
        
        if not shard_products:
            logger.error("No active products found!")
            return []
            
        product_groups = partition_products(shard_products, size=4)
        logger.debug(f"Created {len(product_groups)} websocket groups")
        
        async def start_client(group_id: int, product_group: list) -> Optional[CoinbaseWebSocketClient]:
            if shutdown_event.is_set():
                return None
                
            logger.debug(f"Creating client {group_id} for group: {product_group}")
            
            for attempt in range(3):
                try:
                    client = CoinbaseWebSocketClient(
                        product_group, 
                        f"ws_client_{group_id}", 
                        firestore_service
                    )
                    
                    async with async_timeout.timeout(45):
                        success, status = await client.connect()
                        if success:
                            # Start listening in a background task and store the task
                            client._listen_task = asyncio.create_task(
                                client.listen(),
                                name=f"listen_task_{client.client_id}"
                            )
                            logger.info(f"Started websocket client {group_id} for products: {product_group}")
                            
                            # Verify the task started
                            if client._listen_task.done():
                                exc = client._listen_task.exception()
                                if exc:
                                    logger.error(f"Listen task failed immediately for client {group_id}: {exc}")
                                    continue
                                
                            return client
                        else:
                            logger.error(f"Failed to connect client {group_id}: {status}")
                            continue
                
                except Exception as e:
                    if shutdown_event.is_set():
                        return None
                    logger.error(f"Error creating client {group_id} (attempt {attempt + 1}): {e}")
                    if attempt == 2:
                        logger.error(f"Failed to create client {group_id} after 3 attempts: {str(e)}")
                        return None
                    await asyncio.sleep(5)
            
            return None

        # Start clients in smaller batches
        batch_size = 1
        all_clients = []
        failed_groups = []
        
        for i in range(0, len(product_groups), batch_size):
            if shutdown_event.is_set():
                break
                
            batch = product_groups[i:i + batch_size]
            logger.info(f"Starting batch {i//batch_size} with groups: {batch}")
            
            client_tasks = [
                start_client(j + i, group) 
                for j, group in enumerate(batch)
            ]
            
            try:
                batch_results = await asyncio.gather(*client_tasks, return_exceptions=True)
                
                # Process results
                for j, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        logger.error(f"Batch {i//batch_size} client {j} failed with exception: {result}")
                        failed_groups.append((i + j, batch[j]))
                    elif result is None:
                        logger.error(f"Batch {i//batch_size} client {j} failed to connect")
                        failed_groups.append((i + j, batch[j]))
                    else:
                        all_clients.append(result)
                        logger.info(f"Batch {i//batch_size} client {j} connected successfully")
                
                # Much longer delay between batches
                if i + batch_size < len(product_groups):
                    await asyncio.sleep(10)  # 10 seconds between client starts
                    
            except Exception as e:
                logger.error(f"Batch {i//batch_size} failed: {e}")
                failed_groups.extend([(i + j, group) for j, group in enumerate(batch)])
        
        # Retry failed groups once more
        if failed_groups and not shutdown_event.is_set():
            logger.info(f"Retrying {len(failed_groups)} failed groups...")
            await asyncio.sleep(10)  # Wait before retrying
            
            for group_id, group in failed_groups:
                try:
                    client = await start_client(group_id, group)
                    if client:
                        all_clients.append(client)
                except Exception as e:
                    logger.error(f"Final retry failed for group {group_id}: {e}")
        
        websocket_clients = all_clients
        
        if not websocket_clients:
            logger.error("No websocket clients were successfully created!")
            raise Exception("Failed to create any websocket clients")
            
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
        timeout_keep_alive=60,
        timeout_graceful_shutdown=60,
        loop="auto",
        workers=1,
        limit_concurrency=80,
        limit_max_requests=0,
        backlog=2048,
        h11_max_incomplete_event_size=16384,
        reload=False,
        access_log=False
    )
