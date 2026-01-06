# Design: Go + PostgreSQL Candle Streaming Service

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
|                              Go Candle Streaming Service                          |
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
|                        |   rawCandles channel  |                                  |
|                        |   (buffered: 1000)    |                                  |
|                        +-----------+-----------+                                  |
|                                    |                                              |
|                                    v                                              |
|                        +-----------------------+                                  |
|                        |  Candle Aggregator    |                                  |
|                        |    (goroutine)        |                                  |
|                        |  Aggregates 1m -> Xm  |                                  |
|                        +-----------+-----------+                                  |
|                                    |                                              |
|                    +---------------+----------------+                             |
|                    |                                |                             |
|                    v                                v                             |
|       +------------------------+      +------------------------+                  |
|       |   Batch Writer         |      |   Datastar Hub         |                  |
|       |   (goroutine)          |      |   (goroutine)          |                  |
|       |   Flush: 100ms/50 items|      |   SSE broadcast        |                  |
|       +------------------------+      +------------------------+                  |
|                    |                                |                             |
+-----------------------------------------------------------------------------------+
                     |                                |
                     v                                v
          +-------------------+            +-------------------+
          |   Cloud SQL       |            |    Web Clients    |
          |   PostgreSQL      |            |   (Datastar SSE)  |
          |   + TimescaleDB   |            +-------------------+
          +-------------------+
```

## Go Project Structure

```
spot-server-go/
├── cmd/
│   └── server/
│       └── main.go                 # Application entry point
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
│   │   ├── client.go               # WebSocket client implementation
│   │   ├── messages.go             # Message types and parsing
│   │   └── auth.go                 # JWT authentication for Coinbase
│   │
│   ├── aggregator/
│   │   ├── aggregator.go           # Candle aggregation logic
│   │   └── aggregator_test.go      # Unit tests
│   │
│   ├── storage/
│   │   ├── postgres.go             # PostgreSQL repository
│   │   ├── repository.go           # Repository interface
│   │   └── batch_writer.go         # Batched write optimization
│   │
│   ├── broadcast/
│   │   ├── hub.go                  # Client subscription hub
│   │   └── datastar.go             # Datastar SSE handler
│   │
│   └── api/
│       ├── server.go               # HTTP server setup
│       ├── handlers.go             # Health check, REST endpoints
│       └── middleware.go           # Logging, CORS
│
├── migrations/
│   ├── 001_initial_schema.up.sql
│   └── 001_initial_schema.down.sql
│
├── scripts/
│   ├── deploy.sh                   # Cloud Run deployment
│   └── migrate.sh                  # Database migrations
│
├── Dockerfile
├── docker-compose.yml              # Local development
├── go.mod
├── go.sum
├── Makefile
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
    "spot-server-go/internal/models"
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
    "spot-server-go/internal/models"
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

import "spot-server-go/internal/models"

type Aggregator interface {
    Update(candle *models.Candle) []models.CandleUpdate
    Reset()
}
```

## Datastar SSE Integration (PatchElements)

The server uses Datastar's `PatchElements()` to push custom `<spot-candle>` elements directly to the DOM.
This follows the hypermedia approach where the server drives the frontend by patching HTML elements.

**Client-side note:** The candlestick chart UI will render `<spot-candle>` elements as Datastar Rocket
web components. The chart implementation is **out of scope** for this service.

### SSE Event Format

```
event: datastar-patch-elements
data: elements <spot-candle id="BTC-USD-ONE_MINUTE"
data: elements     data-product="BTC-USD"
data: elements     data-granularity="ONE_MINUTE"
data: elements     data-timestamp="1704567600"
data: elements     data-open="42000.5000000000"
data: elements     data-high="42500.0000000000"
data: elements     data-low="41800.0000000000"
data: elements     data-close="42200.0000000000"
data: elements     data-volume="123.4500000000"
data: elements     data-complete="false"
data: elements ></spot-candle>

```

### Go Implementation

```go
// internal/broadcast/datastar.go
package broadcast

import (
    "fmt"
    "net/http"

    "github.com/starfederation/datastar-go/datastar"
    "spot-server-go/internal/models"
)

type DatastarHandler struct {
    hub *Hub
}

func (h *DatastarHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    // Parse subscription parameters
    productIDs := r.URL.Query()["product"]
    granularities := parseGranularities(r.URL.Query()["granularity"])

    // Create Datastar SSE writer
    sse := datastar.NewSSE(w, r)

    // Create client subscription
    client := &Client{
        ID:            generateID(),
        ProductIDs:    productIDs,
        Granularities: granularities,
        Send:          make(chan *models.CandleUpdate, 100),
    }

    h.hub.Register(client)
    defer h.hub.Unregister(client)

    // Stream updates via Datastar PatchElements
    ctx := r.Context()
    for {
        select {
        case <-ctx.Done():
            return
        case update := <-client.Send:
            // Render candle as custom element for Datastar Rocket component
            sse.PatchElements(renderCandleElement(update))
        }
    }
}

// renderCandleElement generates a <spot-candle> custom element
func renderCandleElement(update *models.CandleUpdate) string {
    c := update.Candle
    return fmt.Sprintf(
        `<spot-candle id="%s-%s"
            data-product="%s"
            data-granularity="%s"
            data-timestamp="%d"
            data-open="%.10f"
            data-high="%.10f"
            data-low="%.10f"
            data-close="%.10f"
            data-volume="%.10f"
            data-complete="%t"
        ></spot-candle>`,
        c.ProductID,
        c.Granularity.String(),
        c.ProductID,
        c.Granularity.String(),
        c.Timestamp.Unix(),
        c.Open,
        c.High,
        c.Low,
        c.Close,
        c.Volume,
        update.IsComplete,
    )
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

    // Channels
    rawCandles := make(chan *models.Candle, 1000)
    aggregatedCandles := make(chan *models.CandleUpdate, 5000)

    // Components
    db := storage.NewPostgresRepository(cfg.DatabaseURL)
    hub := broadcast.NewHub()
    agg := aggregator.NewMemoryAggregator()
    writer := storage.NewBatchWriter(db, 50, 100*time.Millisecond)

    var wg sync.WaitGroup

    // Start hub
    wg.Add(1)
    go func() { defer wg.Done(); hub.Run(ctx) }()

    // Start batch writer
    wg.Add(1)
    go func() { defer wg.Done(); writer.Run(ctx, aggregatedCandles) }()

    // Start aggregator
    wg.Add(1)
    go func() {
        defer wg.Done()
        for {
            select {
            case <-ctx.Done():
                return
            case candle := <-rawCandles:
                for _, update := range agg.Update(candle) {
                    aggregatedCandles <- &update
                    hub.Broadcast(&update)
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

    // Start HTTP server
    wg.Add(1)
    go func() {
        defer wg.Done()
        api.StartServer(ctx, cfg.Port, hub, db)
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
}

func (w *BatchWriter) Run(ctx context.Context, input <-chan *models.CandleUpdate) {
    ticker := time.NewTicker(w.flushInterval)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            w.flush(ctx)
            return
        case update := <-input:
            w.mu.Lock()
            w.buffer = append(w.buffer, update.Candle)
            shouldFlush := len(w.buffer) >= w.batchSize
            w.mu.Unlock()
            if shouldFlush {
                w.flush(ctx)
            }
        case <-ticker.C:
            w.flush(ctx)
        }
    }
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
        - image: gcr.io/PROJECT/spot-server-go:VERSION
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
module spot-server-go

go 1.22

require (
    github.com/starfederation/datastar-go v0.x.x
    github.com/jackc/pgx/v5 v5.x.x
    github.com/gorilla/websocket v1.5.x
    github.com/caarlos0/env/v11 v11.x.x
    github.com/golang-jwt/jwt/v5 v5.x.x
)
```
