# Proposal: Rewrite Spot Server as spot-canvas-app Monorepo

## Why

The current Python/Firestore implementation has throughput limitations that prevent scaling to handle more trading pairs efficiently. Go's superior concurrency model (goroutines, channels) and PostgreSQL's relational capabilities with TimescaleDB time-series optimization will significantly improve performance and enable handling more trading pairs per instance.

## What Changes

### Removed
- **Python codebase** - All Python code (`app/`, `tests/`, `requirements.txt`)
- **Firestore integration** - Replace document database with PostgreSQL
- **Firebase dependencies** - Remove firebase-admin, google-cloud-firestore packages

### Added
- **Monorepo structure** - New `spot-canvas-app/` repo (sibling to `spot-server/`) containing both backend and frontend
- **Go implementation** - Complete rewrite using idiomatic Go patterns based on [Northstar template](https://github.com/zangster300/northstar)
- **NATS messaging** - Embedded NATS server for pub/sub and KV storage (replaces Firestore real-time)
- **PostgreSQL database** - Cloud SQL with TimescaleDB extension for time-series data
- **Templ templates** - Type-safe Go templates for server-rendered HTML
- **Tailwind CSS + DaisyUI** - Styling for hypermedia UI
- **Datastar SSE with PatchElements** - Real-time `<spot-candle>` element updates
- **Datastar Rocket web component** - `<spot-candle>` component for candlestick rendering
- **Taskfile** - Task runner (replaces Makefile) with live reload via Air + esbuild

### Modified
- **Deployment scripts** - Update for Go build and Cloud SQL configuration
- **Cloud Run config** - Add Cloud SQL connection, update container image
- **Environment variables** - Replace Firestore credentials with PostgreSQL connection string

## Impact

### Code Changes
| Area | Current | New |
|------|---------|-----|
| Language | Python 3.11 | Go 1.22+ |
| Web Framework | FastAPI | net/http + chi router |
| Templates | N/A | Templ |
| Database | Firestore | PostgreSQL + TimescaleDB |
| Real-time | Firestore subscriptions | NATS pub/sub + Datastar SSE |
| WebSocket | websockets (Python) | nhooyr.io/websocket |
| Styling | N/A | Tailwind CSS + DaisyUI |
| Build | Makefile | Taskfile + Air + esbuild |

### Client Impact
- **Breaking change**: Clients must migrate from Firestore SDK to SSE API
- **New endpoint**: `/stream?products=BTC-USD&granularities=ONE_MINUTE`
- **Data format**: `<spot-candle>` custom elements via Datastar `PatchElements`
- **Hypermedia approach**: Server renders HTML, patches DOM elements directly
- **Frontend included**: `<spot-candle>` Datastar Rocket component renders candlesticks on canvas/SVG

### Infrastructure Changes
- **New**: Cloud SQL PostgreSQL instance (europe-west1)
- **New**: Database migrations workflow
- **New**: Embedded NATS server (KV bucket for live candle state)
- **Remove**: Firestore indexes and security rules
- **Keep**: Cloud Run sharding architecture (SHARD_INDEX, SHARD_COUNT)

### Deferred
- Historical data ingestion (will add later as separate change)
- Migration of existing Firestore data to PostgreSQL
