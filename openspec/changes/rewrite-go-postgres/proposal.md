# Proposal: Rewrite Spot Server as spot-canvas-app Monorepo

## Why

The current Python/Firestore implementation has throughput limitations that prevent scaling to handle more trading pairs efficiently. Go's superior concurrency model (goroutines, channels) and PostgreSQL's relational capabilities with TimescaleDB time-series optimization will significantly improve performance and enable handling more trading pairs per instance.

## Implementation Phases

This proposal covers **Phase 1 (Backend)** only:

- **Phase 1: Go Backend** (this proposal) - Go server with NATS/PostgreSQL, real-time candle ingestion, SSE streaming
- **Phase 2: Datastar Frontend** (separate proposal) - `<spot-chart>` Datastar Rocket component with SSE chart morphing, replacing rs-charts

## What Changes

### Removed
- **Python codebase** - All Python code (`app/`, `tests/`, `requirements.txt`)
- **Firestore integration** - Replace document database with PostgreSQL
- **Firebase dependencies** - Remove firebase-admin, google-cloud-firestore packages

### Added (Phase 1)
- **Monorepo structure** - New `spot-canvas-app/` repo (sibling to `spot-server/`)
- **Go implementation** - Complete rewrite using idiomatic Go patterns based on [Northstar template](https://github.com/zangster300/northstar)
- **NATS messaging** - Embedded NATS server for pub/sub and KV storage (replaces Firestore real-time)
- **PostgreSQL database** - Cloud SQL with TimescaleDB extension for time-series data
- **Templ templates** - Type-safe Go templates for server-rendered HTML
- **Tailwind CSS + DaisyUI** - Styling for hypermedia UI
- **Datastar SSE** - Real-time candle streaming via Server-Sent Events
- **Taskfile** - Task runner (replaces Makefile) with live reload via Air + esbuild

### Deferred to Phase 2 (Frontend)
- **Datastar Rocket `<spot-chart>` component** - Canvas-based chart rendering with SSE morphing
- **Chart SSE morphing** - Server pushes complete chart state (historical + live candles) via SSE morph
- **Replace rs-charts** - New hypermedia-based chart replaces current Lit web component library

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

### Client Impact (Phase 1)
- **Breaking change**: Clients must migrate from Firestore SDK to SSE API
- **New endpoint**: `/stream?products=BTC-USD&granularities=ONE_MINUTE`
- **Data format**: JSON candle updates via SSE (Phase 2 will add HTML chart morphing)
- **Existing rs-charts**: Can continue using SSE with adapter (Phase 2 will replace with Datastar chart)

### Infrastructure Changes
- **New**: Cloud SQL PostgreSQL instance (europe-west1)
- **New**: Database migrations workflow
- **New**: Embedded NATS server (KV bucket for live candle state)
- **Remove**: Firestore indexes and security rules
- **Keep**: Cloud Run sharding architecture (SHARD_INDEX, SHARD_COUNT)

### Deferred to Separate Proposals
- **Datastar frontend (Phase 2)** - `<spot-chart>` component with SSE chart morphing (no REST API needed - SSE pushes full chart state including historical candles)
- **Historical data ingestion** - Backfill PostgreSQL from Coinbase REST API
- **Firestore migration** - One-time migration of existing data to PostgreSQL
