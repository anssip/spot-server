# Design: spot-canvas-app Monorepo

Based on the [Northstar template](https://github.com/zangster300/northstar) for Datastar + NATS + Go projects.

## Architecture Overview

```
                                    +-------------------+
                                    |   Coinbase API    |
                                    |  (WebSocket API)  |
                                    +--------+----------+
                                             |
                                             | WSS Connection
                                             v
+-----------------------------------------------------------------------------------+
|                              spot-canvas-app (Go Server)                          |
|                                                                                   |
|  +------------------+     +------------------+     +------------------+           |
|  | WebSocket Client |     | WebSocket Client |     | WebSocket Client |  ...      |
|  |  (goroutine)     |     |  (goroutine)     |     |  (goroutine)     |           |
|  +--------+---------+     +--------+---------+     +--------+---------+           |
|           |                        |                        |                     |
|           +------------------------+------------------------+                     |
|                                    |                                              |
|                                    v                                              |
|                        +-----------------------+                                  |
|                        |  Candle Aggregator    |                                  |
|                        |    (goroutine)        |                                  |
|                        |  Aggregates 1m -> Xm  |                                  |
|                        +-----------+-----------+                                  |
|                                    |                                              |
|                    +---------------+----------------+                             |
|                    |               |                |                             |
|                    v               v                v                             |
|       +----------------+  +----------------+  +----------------+                  |
|       | PostgreSQL     |  | NATS Publish   |  | NATS KV Update |                  |
|       | Batch Writer   |  | (subjects)     |  | (live-candles) |                  |
|       +----------------+  +----------------+  +----------------+                  |
|                                    |                                              |
|                                    v                                              |
|                        +------------------------+                                 |
|                        |  Embedded NATS Server  |                                 |
|                        |  - Pub/Sub messaging   |                                 |
|                        |  - KV: live-candles    |                                 |
|                        +-----------+------------+                                 |
|                                    |                                              |
|                                    v                                              |
|                        +------------------------+                                 |
|                        |  SSE Handler           |                                 |
|                        |  (NATS subscription)   |                                 |
|                        |  Datastar PatchElements|                                 |
|                        +------------------------+                                 |
|                                    |                                              |
+-----------------------------------------------------------------------------------+
                     |                                |
                     v                                v
          +-------------------+            +-------------------+
          |   Cloud SQL       |            |    Web Clients    |
          |   PostgreSQL      |            |   (Browser)       |
          |   + TimescaleDB   |            |                   |
          +-------------------+            | <spot-candle>     |
                                           | Datastar Rocket   |
                                           | Canvas/SVG render |
                                           +-------------------+
```

## Monorepo Structure

```
spot-canvas-app/                    # Monorepo root
├── cmd/
│   └── server/
│       └── main.go                 # Application entry point (embeds NATS)
│
├── internal/
│   ├── config/
│   │   └── config.go               # Environment config loading
│   │
│   ├── models/
│   │   ├── candle.go               # Candle struct and methods
│   │   ├── granularity.go          # Granularity enum (1m, 5m, ..., 1d)
│   │   └── product.go              # Trading pair model
│   │
│   ├── coinbase/
│   │   ├── client.go               # WebSocket client (nhooyr.io/websocket)
│   │   ├── messages.go             # Message types and parsing
│   │   └── auth.go                 # JWT authentication for Coinbase
│   │
│   ├── aggregator/
│   │   ├── aggregator.go           # Candle aggregation logic
│   │   └── aggregator_test.go      # Unit tests
│   │
│   ├── nats/
│   │   ├── server.go               # Embedded NATS server setup
│   │   ├── publisher.go            # Publish candles to subjects
│   │   └── kv.go                   # KV bucket operations (live-candles)
│   │
│   ├── storage/
│   │   ├── postgres.go             # PostgreSQL repository (pgx)
│   │   ├── repository.go           # Repository interface
│   │   └── batch_writer.go         # Batched write optimization
│   │
│   ├── handlers/
│   │   ├── sse.go                  # SSE handler (NATS subscription + Datastar)
│   │   ├── pages.go                # Page handlers (Templ templates)
│   │   └── health.go               # Health check endpoint
│   │
│   └── templates/                  # Templ templates (.templ files)
│       ├── layout.templ            # Base layout
│       ├── index.templ             # Home page with Datastar
│       └── components/
│           └── candle.templ        # Server-side candle rendering
│
├── web/
│   ├── static/                     # Static assets
│   │   ├── css/
│   │   │   └── app.css             # Tailwind input
│   │   └── js/
│   │       └── app.js              # Compiled JS (esbuild output)
│   └── components/                 # Phase 2: Datastar Rocket components
│       └── spot-chart.ts           # (Phase 2) Canvas-based chart with SSE morphing
│
├── migrations/
│   ├── 001_initial_schema.up.sql
│   └── 001_initial_schema.down.sql
│
├── scripts/
│   ├── deploy.sh                   # Cloud Run deployment
│   └── migrate.sh                  # Database migrations
│
├── Taskfile.yaml                   # Task runner (replaces Makefile)
├── .air.toml                       # Air live reload config
├── tailwind.config.js              # Tailwind configuration
├── Dockerfile
├── docker-compose.yml              # Local PostgreSQL + TimescaleDB
├── go.mod
├── go.sum
├── CLAUDE.md                       # AI assistant instructions
└── README.md
```

## PostgreSQL Schema (TimescaleDB)

```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Granularity enum
CREATE TYPE granularity AS ENUM (
    'ONE_MINUTE',
    'FIVE_MINUTES',
    'FIFTEEN_MINUTES',
    'THIRTY_MINUTES',
    'ONE_HOUR',
    'TWO_HOURS',
    'SIX_HOURS',
    'ONE_DAY'
);

-- Trading pairs metadata
CREATE TABLE trading_pairs (
    id              SERIAL PRIMARY KEY,
    exchange        VARCHAR(50) NOT NULL DEFAULT 'coinbase',
    product_id      VARCHAR(50) NOT NULL,
    base_currency   VARCHAR(20) NOT NULL,
    quote_currency  VARCHAR(20) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'online',
    min_size        DECIMAL(20, 10),
    max_size        DECIMAL(20, 10),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(exchange, product_id)
);

-- Live candles table (hypertable)
CREATE TABLE live_candles (
    id              BIGSERIAL,
    exchange        VARCHAR(50) NOT NULL DEFAULT 'coinbase',
    product_id      VARCHAR(50) NOT NULL,
    granularity     granularity NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    open            DECIMAL(20, 10) NOT NULL,
    high            DECIMAL(20, 10) NOT NULL,
    low             DECIMAL(20, 10) NOT NULL,
    close           DECIMAL(20, 10) NOT NULL,
    volume          DECIMAL(20, 10) NOT NULL,
    last_update     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (exchange, product_id, granularity, timestamp)
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('live_candles', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Index for efficient queries
CREATE INDEX idx_live_candles_product_granularity
    ON live_candles (exchange, product_id, granularity, timestamp DESC);

CREATE INDEX idx_trading_pairs_status
    ON trading_pairs (exchange, status);
```

## Core Data Models

```go
// internal/models/granularity.go
package models

type Granularity int

const (
    OneMinute Granularity = iota
    FiveMinutes
    FifteenMinutes
    ThirtyMinutes
    OneHour
    TwoHours
    SixHours
    OneDay
)

func (g Granularity) Seconds() int {
    return []int{60, 300, 900, 1800, 3600, 7200, 21600, 86400}[g]
}

func (g Granularity) String() string {
    return []string{
        "ONE_MINUTE", "FIVE_MINUTES", "FIFTEEN_MINUTES", "THIRTY_MINUTES",
        "ONE_HOUR", "TWO_HOURS", "SIX_HOURS", "ONE_DAY",
    }[g]
}

var AllGranularities = []Granularity{
    OneMinute, FiveMinutes, FifteenMinutes, ThirtyMinutes,
    OneHour, TwoHours, SixHours, OneDay,
}
```

```go
// internal/models/candle.go
package models

import "time"

type Candle struct {
    Exchange    string      `json:"exchange"`
    ProductID   string      `json:"product_id"`
    Granularity Granularity `json:"granularity"`
    Timestamp   time.Time   `json:"timestamp"`
    Open        float64     `json:"open"`
    High        float64     `json:"high"`
    Low         float64     `json:"low"`
    Close       float64     `json:"close"`
    Volume      float64     `json:"volume"`
    LastUpdate  time.Time   `json:"last_update"`
}

type CandleUpdate struct {
    Candle     *Candle `json:"candle"`
    IsComplete bool    `json:"is_complete"`
}
```

## Key Interfaces

```go
// internal/storage/repository.go
package storage

import (
    "context"
    "spot-canvas-app/internal/models"
)

type CandleRepository interface {
    UpsertLiveCandle(ctx context.Context, candle *models.Candle) error
    UpsertLiveCandleBatch(ctx context.Context, candles []*models.Candle) error
    GetLiveCandle(ctx context.Context, exchange, productID string,
                  granularity models.Granularity) (*models.Candle, error)
}

type ProductRepository interface {
    GetActiveProducts(ctx context.Context, exchange string) ([]*models.Product, error)
    UpsertProduct(ctx context.Context, product *models.Product) error
}
```

```go
// internal/coinbase/client.go
package coinbase

import (
    "context"
    "spot-canvas-app/internal/models"
)

type CandleHandler func(candle *models.Candle)

type WebSocketClient interface {
    Connect(ctx context.Context) error
    Subscribe(productIDs []string) error
    Listen(ctx context.Context, handler CandleHandler) error
    Close() error
    IsConnected() bool
}
```

```go
// internal/aggregator/aggregator.go
package aggregator

import "spot-canvas-app/internal/models"

type Aggregator interface {
    Update(candle *models.Candle) []models.CandleUpdate
    Reset()
}
```

## NATS Configuration

Embedded NATS server provides pub/sub messaging and KV storage for real-time candle distribution.

### NATS Subjects

```
candles.{product}.{granularity}
```

Examples:
- `candles.BTC-USD.ONE_MINUTE`
- `candles.ETH-USD.ONE_HOUR`
- `candles.*.ONE_MINUTE` (wildcard subscription for all products)

### NATS KV Bucket

**Bucket**: `live-candles`
**Purpose**: Store current candle state for instant SSE initialization

**Key format**: `{product}.{granularity}`
**Value**: JSON-encoded Candle

```go
// internal/nats/kv.go
type CandleKV struct {
    js  nats.JetStreamContext
    kv  nats.KeyValue
}

func (k *CandleKV) Put(candle *models.Candle) error {
    key := fmt.Sprintf("%s.%s", candle.ProductID, candle.Granularity)
    data, _ := json.Marshal(candle)
    _, err := k.kv.Put(key, data)
    return err
}

func (k *CandleKV) Get(productID string, granularity models.Granularity) (*models.Candle, error) {
    key := fmt.Sprintf("%s.%s", productID, granularity)
    entry, err := k.kv.Get(key)
    if err != nil {
        return nil, err
    }
    var candle models.Candle
    json.Unmarshal(entry.Value(), &candle)
    return &candle, nil
}
```

### Embedded NATS Server

```go
// internal/nats/server.go
func StartEmbeddedServer() (*server.Server, error) {
    opts := &server.Options{
        Host:           "127.0.0.1",
        Port:           -1,  // Random available port
        NoLog:          true,
        NoSigs:         true,
        JetStream:      true,
        StoreDir:       "./data/nats",
    }
    ns, err := server.NewServer(opts)
    if err != nil {
        return nil, err
    }
    go ns.Start()
    if !ns.ReadyForConnections(5 * time.Second) {
        return nil, errors.New("nats server not ready")
    }
    return ns, nil
}
```

## Datastar SSE Integration

The server uses Datastar's `MergeFragments()` to push candle data via SSE.
SSE handlers subscribe to NATS subjects and stream updates to connected clients.

**Phase 1 (this proposal)**: SSE streams JSON candle updates for integration with existing clients.

**Phase 2 (future proposal)**: SSE will morph entire `<spot-chart>` component with full chart state (historical + live candles). Server renders chart HTML, pushes via MergeFragments. No REST API needed for historical data - the chart is fully server-rendered.

### SSE Event Format (Phase 1 - JSON)

```
event: candle
data: {"product_id":"BTC-USD","granularity":"ONE_MINUTE","timestamp":1704567600,"open":42000.5,"high":42500.0,"low":41800.0,"close":42200.0,"volume":123.45,"is_complete":false}

```

### SSE Event Format (Phase 2 - HTML Chart Morphing, Future)

In Phase 2, the server will push complete chart state via Datastar MergeFragments:

```
event: datastar-merge-fragments
data: fragments <spot-chart id="chart-BTC-USD-ONE_MINUTE"
data: fragments     data-product="BTC-USD"
data: fragments     data-granularity="ONE_MINUTE">
data: fragments   <!-- Server renders all visible candles (e.g., 100 candles) -->
data: fragments   <canvas data-candles='[{"t":1704567600,"o":42000.5,"h":42500,"l":41800,"c":42200,"v":123.45},...]'></canvas>
data: fragments </spot-chart>

```

### Go Implementation (Phase 1 - JSON SSE)

```go
// internal/handlers/sse.go
package handlers

import (
    "encoding/json"
    "fmt"
    "net/http"

    "github.com/nats-io/nats.go"
    "spot-canvas-app/internal/models"
)

type SSEHandler struct {
    nc *nats.Conn
    kv nats.KeyValue
}

func (h *SSEHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    // Set SSE headers
    w.Header().Set("Content-Type", "text/event-stream")
    w.Header().Set("Cache-Control", "no-cache")
    w.Header().Set("Connection", "keep-alive")

    flusher, ok := w.(http.Flusher)
    if !ok {
        http.Error(w, "Streaming unsupported", http.StatusInternalServerError)
        return
    }

    // Parse subscription parameters
    products := r.URL.Query()["products"]
    granularities := parseGranularities(r.URL.Query()["granularities"])

    // Send initial state from KV bucket
    for _, product := range products {
        for _, gran := range granularities {
            if candle := h.getFromKV(product, gran); candle != nil {
                h.sendCandleEvent(w, flusher, candle, false)
            }
        }
    }

    // Subscribe to NATS subjects
    subs := make([]*nats.Subscription, 0)
    msgChan := make(chan *nats.Msg, 100)

    for _, product := range products {
        for _, gran := range granularities {
            subject := fmt.Sprintf("candles.%s.%s", product, gran)
            sub, _ := h.nc.ChanSubscribe(subject, msgChan)
            subs = append(subs, sub)
        }
    }
    defer func() {
        for _, sub := range subs {
            sub.Unsubscribe()
        }
    }()

    // Stream updates as JSON events
    ctx := r.Context()
    for {
        select {
        case <-ctx.Done():
            return
        case msg := <-msgChan:
            var update models.CandleUpdate
            json.Unmarshal(msg.Data, &update)
            h.sendCandleEvent(w, flusher, update.Candle, update.IsComplete)
        }
    }
}

func (h *SSEHandler) sendCandleEvent(w http.ResponseWriter, f http.Flusher, c *models.Candle, isComplete bool) {
    data, _ := json.Marshal(map[string]interface{}{
        "product_id":  c.ProductID,
        "granularity": c.Granularity.String(),
        "timestamp":   c.Timestamp.Unix(),
        "open":        c.Open,
        "high":        c.High,
        "low":         c.Low,
        "close":       c.Close,
        "volume":      c.Volume,
        "is_complete": isComplete,
    })
    fmt.Fprintf(w, "event: candle\ndata: %s\n\n", data)
    f.Flush()
}
```

## Concurrency Model

```go
// cmd/server/main.go (simplified)
func main() {
    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()

    // Signal handling
    sigChan := make(chan os.Signal, 1)
    signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

    // Start embedded NATS server
    ns, _ := natsserver.StartEmbeddedServer()
    defer ns.Shutdown()

    // Connect to embedded NATS
    nc, _ := nats.Connect(ns.ClientURL())
    defer nc.Close()

    // Create JetStream context and KV bucket
    js, _ := nc.JetStream()
    kv, _ := js.CreateKeyValue(&nats.KeyValueConfig{
        Bucket: "live-candles",
    })

    // Components
    db := storage.NewPostgresRepository(cfg.DatabaseURL)
    agg := aggregator.NewMemoryAggregator()
    writer := storage.NewBatchWriter(db, 50, 100*time.Millisecond)
    publisher := natspkg.NewPublisher(nc, kv)

    // Channels
    rawCandles := make(chan *models.Candle, 1000)

    var wg sync.WaitGroup

    // Start aggregator + publisher
    wg.Add(1)
    go func() {
        defer wg.Done()
        for {
            select {
            case <-ctx.Done():
                return
            case candle := <-rawCandles:
                for _, update := range agg.Update(candle) {
                    // Publish to NATS subject
                    publisher.Publish(&update)
                    // Update KV bucket
                    publisher.UpdateKV(update.Candle)
                    // Write to PostgreSQL (batched)
                    writer.Add(update.Candle)
                }
            }
        }
    }()

    // Start WebSocket clients (sharded)
    products := getShardedProducts(cfg.ShardIndex, cfg.ShardCount)
    for i, group := range partitionProducts(products, 8) {
        wg.Add(1)
        go func(id int, pids []string) {
            defer wg.Done()
            runWebSocketClient(ctx, id, pids, rawCandles)
        }(i, group)
    }

    // Start HTTP server with NATS connection
    wg.Add(1)
    go func() {
        defer wg.Done()
        handlers.StartServer(ctx, cfg.Port, nc, kv, db)
    }()

    // Wait for shutdown
    <-sigChan
    cancel()
    wg.Wait()
}
```

## Batch Writer

```go
// internal/storage/batch_writer.go
type BatchWriter struct {
    repo          CandleRepository
    batchSize     int
    flushInterval time.Duration
    buffer        []*models.Candle
    mu            sync.Mutex
    ctx           context.Context
    cancel        context.CancelFunc
    wg            sync.WaitGroup
}

func NewBatchWriter(repo CandleRepository, batchSize int, flushInterval time.Duration) *BatchWriter {
    ctx, cancel := context.WithCancel(context.Background())
    w := &BatchWriter{
        repo:          repo,
        batchSize:     batchSize,
        flushInterval: flushInterval,
        buffer:        make([]*models.Candle, 0, batchSize),
        ctx:           ctx,
        cancel:        cancel,
    }
    w.wg.Add(1)
    go w.runFlushLoop()
    return w
}

// Add adds a candle to the batch buffer. Flushes automatically when batch is full.
func (w *BatchWriter) Add(candle *models.Candle) {
    w.mu.Lock()
    w.buffer = append(w.buffer, candle)
    shouldFlush := len(w.buffer) >= w.batchSize
    w.mu.Unlock()
    if shouldFlush {
        w.flush()
    }
}

func (w *BatchWriter) runFlushLoop() {
    defer w.wg.Done()
    ticker := time.NewTicker(w.flushInterval)
    defer ticker.Stop()

    for {
        select {
        case <-w.ctx.Done():
            w.flush() // Final flush on shutdown
            return
        case <-ticker.C:
            w.flush()
        }
    }
}

func (w *BatchWriter) flush() {
    w.mu.Lock()
    if len(w.buffer) == 0 {
        w.mu.Unlock()
        return
    }
    candles := w.buffer
    w.buffer = make([]*models.Candle, 0, w.batchSize)
    w.mu.Unlock()

    w.repo.UpsertLiveCandleBatch(w.ctx, candles)
}

func (w *BatchWriter) Close() {
    w.cancel()
    w.wg.Wait()
}
```

## Deployment Configuration

### Cloud Run
```yaml
# Per shard configuration
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"
        autoscaling.knative.dev/maxScale: "1"
        run.googleapis.com/cpu-throttling: "false"
        run.googleapis.com/cloudsql-instances: PROJECT:REGION:INSTANCE
    spec:
      containerConcurrency: 100
      timeoutSeconds: 3600
      containers:
        - image: gcr.io/PROJECT/spot-canvas-app:VERSION
          ports:
            - containerPort: 8080
          resources:
            limits:
              cpu: "1"
              memory: 512Mi
          env:
            - name: SHARD_INDEX
              value: "0"
            - name: SHARD_COUNT
              value: "3"
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: database-url
                  key: latest
```

### Cloud SQL
- **Instance**: PostgreSQL 15 with TimescaleDB
- **Region**: europe-west1
- **Tier**: db-custom-2-4096
- **Storage**: SSD, 20GB initial

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PORT` | HTTP server port | `8080` |
| `DATABASE_URL` | PostgreSQL connection string | `postgres://user:pass@/db?host=/cloudsql/proj:region:inst` |
| `COINBASE_API_KEY` | Coinbase API key | `organizations/...` |
| `COINBASE_PRIVATE_KEY` | Coinbase private key | `-----BEGIN EC PRIVATE KEY-----...` |
| `SHARD_INDEX` | This instance's shard | `0` |
| `SHARD_COUNT` | Total number of shards | `3` |

## Go Dependencies

```go
// go.mod
module spot-canvas-app

go 1.22

require (
    // Web & SSE
    github.com/go-chi/chi/v5 v5.x.x
    github.com/starfederation/datastar-go v0.x.x
    github.com/a-h/templ v0.x.x

    // WebSocket
    nhooyr.io/websocket v1.x.x

    // Database
    github.com/jackc/pgx/v5 v5.x.x

    // NATS
    github.com/nats-io/nats.go v1.x.x
    github.com/nats-io/nats-server/v2 v2.x.x

    // Utilities
    github.com/caarlos0/env/v11 v11.x.x
    github.com/golang-jwt/jwt/v5 v5.x.x
)
```

## Development Dependencies

```json
// package.json (for frontend tooling)
{
  "devDependencies": {
    "tailwindcss": "^3.x.x",
    "daisyui": "^4.x.x",
    "esbuild": "^0.x.x",
    "typescript": "^5.x.x"
  }
}
```

## Taskfile Configuration

```yaml
# Taskfile.yaml
version: '3'

tasks:
  live:
    desc: Start development server with live reload
    deps: [templ, css]
    cmds:
      - air

  build:
    desc: Build production binary
    deps: [templ, css]
    cmds:
      - go build -o bin/server ./cmd/server

  run:
    desc: Run production server
    cmds:
      - ./bin/server

  templ:
    desc: Generate Templ templates
    cmds:
      - templ generate

  css:
    desc: Build Tailwind CSS
    cmds:
      - npx tailwindcss -i ./web/static/css/app.css -o ./web/static/css/output.css

  js:
    desc: Bundle TypeScript with esbuild
    cmds:
      - npx esbuild web/components/*.ts --bundle --outfile=web/static/js/app.js

  migrate:
    desc: Run database migrations
    cmds:
      - ./scripts/migrate.sh up

  test:
    desc: Run tests
    cmds:
      - go test ./...
```
