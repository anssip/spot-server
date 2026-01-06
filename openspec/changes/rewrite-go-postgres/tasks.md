# Tasks: Rewrite Spot Server as spot-canvas-app Monorepo

> **Scope:** This task list covers Phase 1 (Go Backend). Phase 8 (Datastar frontend) is deferred to a separate proposal.

## Phase 1: Project Scaffold (Northstar Stack)

- [ ] 1.1 Create monorepo at `~/Documents/projects/spot-canvas/spot-canvas-app/`
- [ ] 1.2 Initialize Go module (`go mod init spot-canvas-app`)
- [ ] 1.3 Create Taskfile.yaml with tasks: `live`, `build`, `run`, `templ`, `css`, `js`
- [ ] 1.4 Configure Air live reload (`.air.toml`)
- [ ] 1.5 Set up esbuild for TypeScript bundling (`package.json`)
- [ ] 1.6 Configure Tailwind CSS + DaisyUI (`tailwind.config.js`)
- [ ] 1.7 Create base Templ templates (`internal/templates/layout.templ`, `index.templ`)
- [ ] 1.8 Create docker-compose.yml for local PostgreSQL + TimescaleDB
- [ ] 1.9 Create Dockerfile (multi-stage build)
- [ ] 1.10 Set up config package with environment variable loading
- [ ] 1.11 Create CLAUDE.md with project instructions
- [ ] 1.12 Set up .gitignore, .env.example
- [ ] 1.13 Move `openspec/` from spot-server to spot-canvas-app
- [ ] 1.14 Move `AGENTS.md` to spot-canvas-app root (or openspec/)

## Phase 2: NATS + Database Layer

- [ ] 2.1 Set up embedded NATS server (`internal/nats/server.go`)
- [ ] 2.2 Create NATS KV bucket `live-candles` (`internal/nats/kv.go`)
- [ ] 2.3 Implement NATS publisher for candle subjects (`internal/nats/publisher.go`)
- [ ] 2.4 Create migration 001_initial_schema.up.sql with TimescaleDB setup
- [ ] 2.5 Create migration 001_initial_schema.down.sql
- [ ] 2.6 Implement PostgreSQL repository with pgx driver
- [ ] 2.7 Implement UpsertLiveCandle with INSERT ON CONFLICT UPDATE
- [ ] 2.8 Implement UpsertLiveCandleBatch for batched writes
- [ ] 2.9 Implement GetActiveProducts query
- [ ] 2.10 Implement BatchWriter with flush interval and batch size
- [ ] 2.11 Write unit tests for NATS and repository layers

## Phase 3: Data Models

- [ ] 3.1 Create Granularity type with Seconds() and String() methods
- [ ] 3.2 Create Candle struct with JSON tags
- [ ] 3.3 Create CandleUpdate struct (Candle + IsComplete flag)
- [ ] 3.4 Create Product struct for trading pair metadata
- [ ] 3.5 Write unit tests for model methods

## Phase 4: Coinbase WebSocket Client

- [ ] 4.1 Implement JWT authentication for Coinbase Advanced Trade API
- [ ] 4.2 Create WebSocket client with nhooyr.io/websocket
- [ ] 4.3 Implement Connect() with timeout and retry logic
- [ ] 4.4 Implement Subscribe() for candles channel (5 products: BTC-USD, ETH-USD, ADA-USD, DOGE-USD, SOL-USD)
- [ ] 4.5 Implement Listen() with message parsing
- [ ] 4.6 Implement exponential backoff reconnection
- [ ] 4.7 Implement graceful Close() with context cancellation
- [ ] 4.8 Write integration tests with mock WebSocket server

## Phase 5: Candle Aggregator

- [ ] 5.1 Implement in-memory aggregator with map[key]Candle
- [ ] 5.2 Implement Update() that processes 1m candle into all granularities
- [ ] 5.3 Implement interval timestamp calculation (align to granularity boundary)
- [ ] 5.4 Implement candle completion detection
- [ ] 5.5 Implement memory cleanup for completed candles
- [ ] 5.6 Implement Reset() for connection recovery
- [ ] 5.7 Write unit tests for aggregation logic

## Phase 6: Datastar SSE Handler (NATS Subscription)

- [ ] 6.1 Create SSE handler with NATS subscription (`internal/handlers/sse.go`)
- [ ] 6.2 Implement subscription parameter parsing (products, granularities)
- [ ] 6.3 Send initial state from NATS KV bucket on connection
- [ ] 6.4 Subscribe to NATS subjects based on query params
- [ ] 6.5 Implement renderCandleElement() to generate `<spot-candle>` custom elements
- [ ] 6.6 Implement MergeFragments() to push candle elements to clients
- [ ] 6.7 Handle client disconnection and cleanup NATS subscriptions
- [ ] 6.8 Write integration tests for SSE streaming with element patching

## Phase 7: HTTP Server + Routes

- [ ] 7.1 Create HTTP server with chi router and graceful shutdown
- [ ] 7.2 Implement /health endpoint with NATS and DB connection status
- [ ] 7.3 Implement /stream SSE endpoint (Datastar handler)
- [ ] 7.4 Implement / page handler (renders index.templ)
- [ ] 7.5 Set up static file serving for CSS/JS
- [ ] 7.6 Add CORS middleware
- [ ] 7.7 Add request logging middleware
- [ ] 7.8 Write API endpoint tests

## Phase 8: spot-chart Web Component (DEFERRED TO PHASE 2)

> **Note:** This phase is deferred to a separate Phase 2 proposal. Phase 1 focuses on the Go backend only.

- [ ] 8.1 Create Datastar Rocket `<spot-chart>` component (`web/components/spot-chart.ts`)
- [ ] 8.2 Implement canvas-based multi-candle chart rendering
- [ ] 8.3 Handle SSE chart morphing (server pushes full chart state)
- [ ] 8.4 Style component with Tailwind classes
- [ ] 8.5 Replace rs-charts with new Datastar chart
- [ ] 8.6 Write component tests

## Phase 9: Application Orchestration

- [ ] 9.1 Implement main.go with embedded NATS server initialization
- [ ] 9.2 Connect to NATS and create JetStream/KV
- [ ] 9.3 Set up aggregator → NATS publish → PostgreSQL write pipeline
- [ ] 9.4 Implement signal handling (SIGINT, SIGTERM)
- [ ] 9.5 Implement graceful shutdown with WaitGroup
- [ ] 9.6 Implement product sharding (SHARD_INDEX, SHARD_COUNT)
- [ ] 9.7 Implement product partitioning (8 products per WS client)
- [ ] 9.8 Implement staggered client startup to avoid rate limits

## Phase 10: Cloud Infrastructure

- [ ] 10.1 Create Cloud SQL PostgreSQL instance with TimescaleDB
- [ ] 10.2 Configure Cloud SQL connection from Cloud Run (Unix socket)
- [ ] 10.3 Store DATABASE_URL and COINBASE credentials in Secret Manager
- [ ] 10.4 Update deploy.sh for Go build and Cloud SQL
- [ ] 10.5 Update cloudbuild.yaml for multi-shard deployment
- [ ] 10.6 Create migrate.sh for running database migrations

## Phase 11: Testing & Validation

- [ ] 11.1 Run full test suite with coverage
- [ ] 11.2 Test local development with docker-compose and `task live`
- [ ] 11.3 Deploy to staging environment
- [ ] 11.4 Validate candle data accuracy against Python service
- [ ] 11.5 Load test with multiple simultaneous SSE clients
- [ ] 11.6 Verify graceful shutdown behavior

## Phase 12: Cleanup

- [ ] 12.1 Archive Python spot-server (keep until Go version stable)
- [ ] 12.2 Update README.md with monorepo instructions
- [ ] 12.3 Remove Firestore-related configuration files
- [ ] 12.4 Update openspec/project.md with new tech stack
