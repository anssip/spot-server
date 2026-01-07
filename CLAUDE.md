<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Spot Server is a real-time cryptocurrency price tracking service that:
1. Connects to Coinbase WebSocket API to receive live candle data for multiple trading pairs
2. Aggregates candles across multiple timeframes (1m, 5m, 15m, 30m, 1h, 2h, 6h, 1d)
3. Stores live candles in Google Cloud Firestore for real-time client subscriptions
4. Provides REST API endpoints via FastAPI
5. Deployed to Google Cloud Run with sharding support for horizontal scaling

## Architecture

### Core Components

1. **WebSocket Client Layer** (`app/services/candles/websocket_client.py`)
   - `CoinbaseWebSocketClient`: Manages persistent WebSocket connections to Coinbase
   - `CandleAggregator`: Aggregates 1-minute candles into multiple timeframes
   - Multiple clients run in parallel, each handling a subset of trading pairs (default: 8 products per client)

2. **Data Layer** (`app/services/candles/firestore_service.py`)
   - `FirestoreService`: Singleton service for Firestore operations
   - Writes live candles to `exchanges/{exchange}/products/{product_id}/intervals/{granularity}` path
   - Manages product metadata in `trading_pairs/exchanges` document

3. **API Layer** (`app/main.py`)
   - FastAPI application with async lifecycle management
   - Health check endpoint for Cloud Run monitoring
   - Background initialization of WebSocket clients during startup

4. **Data Ingestion** (`app/ingest.py`, `app/services/ingest/candle_history.py`)
   - Historical candle ingestion from Coinbase REST API
   - Used for backfilling historical data

### Sharding Architecture

The server supports horizontal scaling via sharding:
- Environment variables `SHARD_COUNT` and `SHARD_INDEX` control product distribution
- Each shard handles a subset of trading pairs
- Deploy multiple Cloud Run instances with different shard indices
- Currently configured for 1 shard, but can scale up

### Data Models

- **Candle** (`app/services/candles/models.py`): Core data structure with OHLCV data
- **Granularity**: Enum defining supported timeframes (1m to 1d)
- **Product**: Dataclass for trading pair metadata

## Build and Test Commands

```bash
# Run development server (requires activated venv)
make dev

# Install dependencies
make install

# Run all tests
make test

# Run a single test file
pytest tests/services/candles/test_coinbase.py

# Run a specific test
pytest tests/services/candles/test_coinbase.py::test_function_name

# Code quality
make lint  # runs flake8 and black

# Clean Python cache files
make clean

# Deploy Firestore rules
make firestore-rules

# Deploy Firestore indexes
make firestore-indexes

# Run historical data ingestion
make ingest
```

## Deployment

The project deploys to Google Cloud Run using Cloud Build:

```bash
# Deploy using helper script (generates cloudbuild.yaml dynamically)
./scripts/deploy.sh

# Or use make
make deploy
```

The deployment:
- Builds Docker image and pushes to Artifact Registry
- Deploys to Cloud Run with 512Mi memory, 80 concurrency
- Uses Gen2 execution environment with CPU boost
- Maintains minimum 1 instance (always warm)
- Configures SHARD_COUNT and SHARD_INDEX environment variables

## Environment Configuration

Required environment variables (use `.env` file locally):
- `COINBASE_API_KEY`: Coinbase API key
- `COINBASE_PRIVATE_KEY`: Coinbase API secret
- `PROJECT_ID`: Google Cloud project ID (production only)
- `SHARD_COUNT`: Number of shards (default: 10)
- `SHARD_INDEX`: This instance's shard index (default: 0)

Credentials are managed via Google Secret Manager in production.

## Firestore Data Model

```
firestore/
├── trading_pairs/
│   └── exchanges/  # Document containing map of all exchanges
│       └── coinbase/  # Map field
│           └── {product_id}/  # e.g., BTC-USD
│               ├── base_currency
│               ├── quote_currency
│               ├── status (online|delisted)
│               ├── min_size
│               └── max_size
│
└── exchanges/
    └── {exchange}/  # e.g., coinbase
        └── products/
            └── {product_id}/  # e.g., BTC-USD
                └── intervals/
                    └── {granularity}/  # e.g., ONE_MINUTE, ONE_HOUR
                        ├── timestamp (candle start time)
                        ├── open
                        ├── high
                        ├── low
                        ├── close
                        ├── volume
                        └── lastUpdate (server timestamp)
```

## Code Style Guidelines

- **Python**: Follow PEP 8 style guide
- **Type hints**: Use typing module for all function parameters and returns
- **Imports**: Group standard library, third-party, and local imports
- **Logging**: Use module-level logger via `logging.getLogger(__name__)`, not print statements
- **Error handling**: Use try/except blocks with specific exceptions
- **Async**: Project uses async/await pattern throughout with FastAPI and asyncio
- **Data models**: Use dataclasses for internal models (Candle, Product), Pydantic for API models
- **Testing**: Tests use pytest with asyncio support (configured in pytest.ini)

## Key Implementation Details

1. **WebSocket Connection Management**
   - Clients partition products into groups of 8 for better performance
   - Automatic reconnection with exponential backoff
   - Health checks monitor connection status and message gaps
   - Graceful shutdown via signal handlers (SIGINT, SIGTERM)

2. **Candle Aggregation**
   - All granularities are computed from 1-minute base candles
   - Candles are "completed" when the interval boundary is crossed
   - Completed candles are removed from memory to prevent leaks

3. **Firestore Operations**
   - FirestoreService uses singleton pattern to share DB client
   - Live candles use `set(merge=True)` to update without overwriting
   - Currently tracking specific pairs: BTC-USD, ETH-USD, ADA-USD, DOGE-USD, SOL-USD

4. **Startup Process**
   - Health endpoint returns 200 during startup to prevent Cloud Run termination
   - WebSocket clients initialize in background during lifespan
   - Clients start in batches with 10-second delays to avoid rate limits
   - Failed clients are retried once before giving up

## Tasks and issues tracking

Use 'bd' for task tracking
