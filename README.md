# Spot Server

Real-time cryptocurrency price tracking service that streams live candle data from Coinbase and stores it in Google Cloud Firestore for client subscriptions.

## Features

- **Real-time WebSocket streaming** from Coinbase Advanced Trade API
- **Multi-timeframe aggregation** (1m, 5m, 15m, 30m, 1h, 2h, 6h, 1d)
- **Cloud-native deployment** on Google Cloud Run with horizontal scaling
- **Firestore integration** for real-time client subscriptions
- **High availability** with health monitoring and automatic reconnection

## Quick Start

### Prerequisites

- Python 3.9+
- Google Cloud account with Firestore enabled
- Coinbase Advanced Trade API credentials

### Installation

```bash
# Install dependencies
make install

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials
```

### Development

```bash
# Run development server
make dev

# Run tests
make test

# Code formatting and linting
make lint
```

## Deployment

Deploy to Google Cloud Run:

```bash
./scripts/deploy.sh
```

The deployment script builds a Docker image and deploys it to Cloud Run with automatic scaling and health monitoring.

## Architecture

Spot Server uses a sharded architecture to handle multiple trading pairs efficiently:

- **WebSocket Layer**: Manages persistent connections to Coinbase, partitioned across multiple clients
- **Aggregation Layer**: Computes candles for all timeframes from 1-minute base data
- **Storage Layer**: Firestore for real-time updates and historical data
- **API Layer**: FastAPI with async support and health monitoring

For detailed architecture documentation, see [CLAUDE.md](CLAUDE.md).

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `COINBASE_API_KEY` | Coinbase API key | Yes |
| `COINBASE_PRIVATE_KEY` | Coinbase API secret | Yes |
| `PROJECT_ID` | Google Cloud project ID | Production only |
| `SHARD_COUNT` | Number of server shards | No (default: 10) |
| `SHARD_INDEX` | This instance's shard index | No (default: 0) |

## API Endpoints

- `GET /health` - Health check endpoint for monitoring

## Related Projects

This library is part of the Spot Canvas "ecosystem":

- [sc-app – Spot Canvas website and charts application with AI Assistend technical analysis](https://github.com/anssipiirainen/sc-app)
- [rc-charts – The charting library this app uses](https://github.com/anssipiirainen/sc-app)
- [market-evaluators – Indicators backend for Spot Canvas and this library](https://github.com/anssipiirainen/market-evaluators)

## License

MIT
