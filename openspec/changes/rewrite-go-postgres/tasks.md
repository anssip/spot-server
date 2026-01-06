# Tasks: Rewrite Spot Server in Go with PostgreSQL

## Phase 1: Project Setup

- [ ] 1.1 Create Go project structure (`spot-server-go/`)
- [ ] 1.2 Initialize go.mod with module name and Go version
- [ ] 1.3 Create Makefile with dev, build, test, lint targets
- [ ] 1.4 Create docker-compose.yml for local PostgreSQL + TimescaleDB
- [ ] 1.5 Create Dockerfile for Go application
- [ ] 1.6 Set up config package with environment variable loading

## Phase 2: Database Layer

- [ ] 2.1 Create migration 001_initial_schema.up.sql with TimescaleDB setup
- [ ] 2.2 Create migration 001_initial_schema.down.sql
- [ ] 2.3 Implement PostgreSQL repository with pgx driver
- [ ] 2.4 Implement UpsertLiveCandle with INSERT ON CONFLICT UPDATE
- [ ] 2.5 Implement UpsertLiveCandleBatch for batched writes
- [ ] 2.6 Implement GetActiveProducts query
- [ ] 2.7 Implement BatchWriter with flush interval and batch size
- [ ] 2.8 Write unit tests for repository layer

## Phase 3: Data Models

- [ ] 3.1 Create Granularity type with Seconds() and String() methods
- [ ] 3.2 Create Candle struct with JSON tags
- [ ] 3.3 Create CandleUpdate struct (Candle + IsComplete flag)
- [ ] 3.4 Create Product struct for trading pair metadata
- [ ] 3.5 Write unit tests for model methods

## Phase 4: Coinbase WebSocket Client

- [ ] 4.1 Implement JWT authentication for Coinbase Advanced Trade API
- [ ] 4.2 Create WebSocket client with gorilla/websocket
- [ ] 4.3 Implement Connect() with timeout and retry logic
- [ ] 4.4 Implement Subscribe() for candles channel
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

## Phase 6: Datastar SSE Broadcast (PatchElements)

- [ ] 6.1 Create Hub struct for managing client subscriptions
- [ ] 6.2 Implement Register() and Unregister() for clients
- [ ] 6.3 Implement Broadcast() with product/granularity filtering
- [ ] 6.4 Create Datastar SSE handler using datastar-go
- [ ] 6.5 Implement subscription parameter parsing (product, granularity)
- [ ] 6.6 Implement renderCandleElement() to generate `<spot-candle>` custom elements
- [ ] 6.7 Implement PatchElements() to push candle elements to clients
- [ ] 6.8 Write integration tests for SSE streaming with element patching

## Phase 7: HTTP API

- [ ] 7.1 Create HTTP server with graceful shutdown
- [ ] 7.2 Implement /health endpoint with connection status
- [ ] 7.3 Implement /api/v1/stream SSE endpoint (Datastar handler)
- [ ] 7.4 Implement /api/v1/products REST endpoint
- [ ] 7.5 Add CORS middleware
- [ ] 7.6 Add request logging middleware
- [ ] 7.7 Write API endpoint tests

## Phase 8: Application Orchestration

- [ ] 8.1 Implement main.go with component initialization
- [ ] 8.2 Set up channel pipeline (rawCandles → aggregatedCandles)
- [ ] 8.3 Implement signal handling (SIGINT, SIGTERM)
- [ ] 8.4 Implement graceful shutdown with WaitGroup
- [ ] 8.5 Implement product sharding (SHARD_INDEX, SHARD_COUNT)
- [ ] 8.6 Implement product partitioning (8 products per WS client)
- [ ] 8.7 Implement staggered client startup to avoid rate limits

## Phase 9: Cloud Infrastructure

- [ ] 9.1 Create Cloud SQL PostgreSQL instance with TimescaleDB
- [ ] 9.2 Configure Cloud SQL connection from Cloud Run
- [ ] 9.3 Store DATABASE_URL in Secret Manager
- [ ] 9.4 Update deploy.sh for Go build and Cloud SQL
- [ ] 9.5 Update cloudbuild.yaml for multi-shard deployment
- [ ] 9.6 Create migrate.sh for running database migrations

## Phase 10: Testing & Validation

- [ ] 10.1 Run full test suite with coverage
- [ ] 10.2 Test local development with docker-compose
- [ ] 10.3 Deploy to staging environment
- [ ] 10.4 Validate candle data accuracy against Python service
- [ ] 10.5 Load test with multiple simultaneous SSE clients
- [ ] 10.6 Verify graceful shutdown behavior

## Phase 11: Cleanup

- [ ] 11.1 Archive Python codebase (or delete after validation)
- [ ] 11.2 Update README.md with Go-specific instructions
- [ ] 11.3 Update CLAUDE.md with new architecture documentation
- [ ] 11.4 Remove Firestore-related configuration files
- [ ] 11.5 Update openspec/project.md with new tech stack
