# Proposal: Rewrite Spot Server in Go with PostgreSQL

## Why

The current Python/Firestore implementation has throughput limitations that prevent scaling to handle more trading pairs efficiently. Go's superior concurrency model (goroutines, channels) and PostgreSQL's relational capabilities with TimescaleDB time-series optimization will significantly improve performance and enable handling more trading pairs per instance.

## What Changes

### Removed
- **Python codebase** - All Python code (`app/`, `tests/`, `requirements.txt`)
- **Firestore integration** - Replace document database with PostgreSQL
- **Firebase dependencies** - Remove firebase-admin, google-cloud-firestore packages

### Added
- **Go implementation** - Complete rewrite using idiomatic Go patterns
- **PostgreSQL database** - Cloud SQL with TimescaleDB extension for time-series data
- **Datastar SSE with PatchElements** - Real-time `<spot-candle>` element updates (replaces Firestore subscriptions)
- **New project structure** - Go standard layout with `cmd/`, `internal/`, `migrations/`

### Modified
- **Deployment scripts** - Update for Go build and Cloud SQL configuration
- **Cloud Run config** - Add Cloud SQL connection, update container image
- **Environment variables** - Replace Firestore credentials with PostgreSQL connection string

## Impact

### Code Changes
| Area | Current | New |
|------|---------|-----|
| Language | Python 3.11 | Go 1.22+ |
| Web Framework | FastAPI | net/http + chi/mux |
| Database | Firestore | PostgreSQL + TimescaleDB |
| Real-time | Firestore subscriptions | Datastar SSE |
| WebSocket | websockets (Python) | gorilla/websocket |

### Client Impact
- **Breaking change**: Clients must migrate from Firestore SDK to SSE API
- **New endpoint**: `/api/v1/stream?product=BTC-USD&granularity=ONE_MINUTE`
- **Data format**: `<spot-candle>` custom elements via Datastar `PatchElements`
- **Hypermedia approach**: Server patches DOM elements directly, not JSON signals
- **Client rendering**: Candle elements rendered as Datastar Rocket web components (chart UI out of scope)

### Infrastructure Changes
- **New**: Cloud SQL PostgreSQL instance (europe-west1)
- **New**: Database migrations workflow
- **Remove**: Firestore indexes and security rules
- **Keep**: Cloud Run sharding architecture (SHARD_INDEX, SHARD_COUNT)

### Deferred
- Historical data ingestion (will add later as separate change)
- Migration of existing Firestore data to PostgreSQL
