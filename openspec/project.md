# Project Context

## Purpose
Spot Server is a real-time cryptocurrency price tracking service that:
- Connects to Coinbase WebSocket API to receive live candle data for multiple trading pairs
- Aggregates candles across multiple timeframes (1m, 5m, 15m, 30m, 1h, 2h, 6h, 1d)
- Stores live candles in Google Cloud Firestore for real-time client subscriptions
- Provides REST API endpoints for health monitoring and data access
- Supports horizontal scaling via sharding architecture

## Tech Stack
- **Language**: Python 3.x with async/await
- **Web Framework**: FastAPI
- **Database**: Google Cloud Firestore
- **Deployment**: Google Cloud Run (Docker containers)
- **Build**: Cloud Build with Artifact Registry
- **Testing**: pytest with asyncio support
- **Code Quality**: flake8, black

## Project Conventions

### Code Style
- Follow PEP 8 style guide
- Use type hints (typing module) for all function parameters and returns
- Group imports: standard library, third-party, local (separated by blank lines)
- Use module-level logger via `logging.getLogger(__name__)`, not print statements
- Error handling with try/except blocks using specific exceptions
- Use dataclasses for internal models (Candle, Product), Pydantic for API models

### Architecture Patterns
- **Singleton Pattern**: FirestoreService uses singleton to share DB client
- **Sharding**: Horizontal scaling via SHARD_COUNT/SHARD_INDEX environment variables
- **WebSocket Client Partitioning**: Products grouped into batches of 8 per client
- **Background Initialization**: WebSocket clients start during FastAPI lifespan with staggered delays
- **Graceful Shutdown**: Signal handlers for SIGINT/SIGTERM

### Testing Strategy
- Tests use pytest with asyncio support (configured in pytest.ini)
- Test files located in `tests/` directory mirroring source structure
- Run all tests: `make test`
- Run single file: `pytest tests/path/to/test_file.py`
- Run specific test: `pytest tests/path/to/test_file.py::test_function_name`

### Git Workflow
- Main branch: `main`
- Deployment triggered via `./scripts/deploy.sh` or `make deploy`

## Domain Context
- **Candle/OHLCV Data**: Open, High, Low, Close, Volume price data for trading pairs
- **Granularity**: Timeframe intervals (ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE, etc.)
- **Trading Pairs**: Cryptocurrency pairs like BTC-USD, ETH-USD, SOL-USD
- **Candle Aggregation**: Higher timeframes computed from 1-minute base candles
- **Candle Completion**: Candles finalized when interval boundary crossed

## Important Constraints
- **Rate Limits**: Coinbase API rate limits require staggered client initialization (10-second delays)
- **Cloud Run**: Health endpoint must return 200 during startup to prevent termination
- **Memory**: Completed candles removed from memory to prevent leaks
- **Batch Size**: Maximum 8 products per WebSocket client for performance

## External Dependencies
- **Coinbase WebSocket API**: Real-time candle data source
- **Coinbase REST API**: Historical candle backfill (ingest)
- **Google Cloud Firestore**: Primary database for live candle storage
- **Google Secret Manager**: Credential management in production
- **Google Artifact Registry**: Docker image storage
- **Google Cloud Run**: Container hosting platform
