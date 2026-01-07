# Design: spot-canvas-app Monorepo

Based on the [Northstar template](https://github.com/zangster300/northstar) for Datastar + NATS + Go projects.

## Architecture Overview

```
                                    +-------------------+
                                    |   Coinbase API    |
                                    |  (WebSocket API)  |
                                    +--------+----------+
                                             |
                                             | 25 WSS Connections (20 products each)
                                             v
+-----------------------------------------------------------------------------------+
|                              spot-canvas-app (Go Server)                          |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                     Connection Manager                                       |  |
|  |  +---------------+  +---------------+  +---------------+                     |  |
|  |  | WS Client 1   |  | WS Client 2   |  | WS Client N   |  (20 products each) |  |
|  |  | buffer: 100   |  | buffer: 100   |  | buffer: 100   |                     |  |
|  |  +-------+-------+  +-------+-------+  +-------+-------+                     |  |
|  |          |                  |                  |                             |  |
|  |          +------------------+------------------+                             |  |
|  |                             | Raw Candle Channel (buffer: 2000)              |  |
|  +-----------------------------------------------------------------------------+  |
|                                |                                                  |
|                                v                                                  |
|  +-----------------------------------------------------------------------------+  |
|  |                     Sharded Aggregator (16 shards)                           |  |
|  |  +----------+  +----------+  +----------+  +----------+                      |  |
|  |  | Shard 0  |  | Shard 1  |  | Shard 2  |  | ...      |  FNV-1a hash routing |  |
|  |  | buf: 256 |  | buf: 256 |  | buf: 256 |  |          |  by product ID       |  |
|  |  +----+-----+  +----+-----+  +----+-----+  +----------+                      |  |
|  |       |             |             |                                          |  |
|  |       +-------------+-------------+                                          |  |
|  |                     | Update Channel (buffer: 1000)                          |  |
|  +-----------------------------------------------------------------------------+  |
|                        |                                                          |
|        +---------------+---------------+---------------+                          |
|        |               |               |               |                          |
|        v               v               v               v                          |
|  +-----------+  +-------------+  +-----------+  +------------------+              |
|  | Batch     |  | NATS        |  | NATS KV   |  | Backpressure     |              |
|  | Writer    |  | Publisher   |  | Updater   |  | Monitor          |              |
|  | 100/50ms  |  | (immediate) |  | 10ms dupe |  | 80% threshold    |              |
|  +-----------+  +-------------+  +-----------+  +------------------+              |
|        |               |               |                                          |
|        v               v               v                                          |
|  +-----------+  +------------------------+                                        |
|  | TimescaleDB|  |  Embedded NATS Server  |                                        |
|  | PostgreSQL |  |  - Pub/Sub messaging   |                                        |
|  +-----------+  |  - KV: live-candles    |                                        |
|                 +-----------+------------+                                        |
|                             |                                                     |
|                             v                                                     |
|                 +------------------------+                                        |
|                 |  SSE Handler           |                                        |
|                 |  (NATS subscription)   |                                        |
|                 |  Target: <100ms e2e    |                                        |
|                 +------------------------+                                        |
|                             |                                                     |
+-----------------------------------------------------------------------------------+
                              v
                   +-------------------+
                   |    Web Clients    |
                   |   (Browser)       |
                   +-------------------+
```

### Performance Targets

| Metric | Target |
|--------|--------|
| Products per instance | 500 |
| WebSocket connections | 25 (20 products each) |
| WebSocket to SSE latency | <100ms |
| Database batch size | 100 rows |
| Database flush interval | 50ms |
| Aggregator shards | 16 |
| Channel high-water mark | 80% |

## Monorepo Structure

```
spot-canvas-app/                    # Monorepo root
├── cmd/
│   └── server/
│       └── main.go                 # Application entry point (embeds NATS)
│
├── internal/
│   ├── config/
│   │   ├── config.go               # Environment config loading
│   │   └── buffers.go              # Buffer sizing configuration
│   │
│   ├── models/
│   │   ├── candle.go               # Candle struct and methods
│   │   ├── granularity.go          # Granularity enum (1m, 5m, ..., 1d)
│   │   └── product.go              # Trading pair model
│   │
│   ├── coinbase/
│   │   ├── client.go               # WebSocket client (nhooyr.io/websocket)
│   │   ├── connection_manager.go   # Multi-connection management (20 products/conn)
│   │   ├── messages.go             # Message types and parsing
│   │   └── auth.go                 # JWT authentication for Coinbase
│   │
│   ├── aggregator/
│   │   ├── aggregator.go           # Aggregator interface
│   │   ├── sharded_aggregator.go   # 16-shard parallel aggregator
│   │   └── aggregator_test.go      # Unit tests
│   │
│   ├── metrics/
│   │   ├── metrics.go              # Prometheus metrics definitions
│   │   └── backpressure.go         # Backpressure detection and monitoring
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

## Connection Manager

Manages multiple WebSocket connections to Coinbase, with 20 products per connection (the Coinbase maximum). This reduces the number of connections from 63 to 25 for 500 products.

### Coinbase API Constraints

- **20 subscriptions per connection** (Coinbase limit)
- **1 connection per second** recommended for new connections
- **750 connections per second** hard limit per IP

### Implementation

```go
// internal/coinbase/connection_manager.go
package coinbase

import (
    "context"
    "sync"
    "sync/atomic"
    "time"

    "spot-canvas-app/internal/models"
)

const (
    ProductsPerConnection = 20      // Coinbase maximum
    ConnectionRateLimit   = 1       // 1 connection per second
    MaxConnections        = 50      // Per instance (1000 products / 20)
    ReadBufferSize        = 100     // Per-connection message buffer
    ReconnectBackoffBase  = 2 * time.Second
    ReconnectBackoffMax   = 60 * time.Second
)

type ConnectionManager struct {
    connections []*WebSocketClient
    products    map[string]*WebSocketClient  // product -> connection mapping
    mu          sync.RWMutex

    // Output channel (bounded to prevent memory issues)
    outputChan  chan *models.Candle
    dropCounter atomic.Int64

    ctx    context.Context
    cancel context.CancelFunc
}

func NewConnectionManager(outputChanSize int) *ConnectionManager {
    ctx, cancel := context.WithCancel(context.Background())
    return &ConnectionManager{
        connections: make([]*WebSocketClient, 0),
        products:    make(map[string]*WebSocketClient),
        outputChan:  make(chan *models.Candle, outputChanSize),
        ctx:         ctx,
        cancel:      cancel,
    }
}

// Start initializes all WebSocket connections with rate limiting
func (cm *ConnectionManager) Start(products []string, auth *Auth) error {
    groups := partitionProducts(products, ProductsPerConnection)

    for i, group := range groups {
        client := NewWebSocketClient(group, auth, cm.outputChan)
        cm.connections = append(cm.connections, client)

        for _, product := range group {
            cm.products[product] = client
        }

        go client.Run(cm.ctx)

        // Rate limit: 1 connection per second
        if i < len(groups)-1 {
            time.Sleep(time.Second)
        }
    }

    return nil
}

// Output returns the channel of received candles
func (cm *ConnectionManager) Output() <-chan *models.Candle {
    return cm.outputChan
}

func (cm *ConnectionManager) Close() {
    cm.cancel()
    for _, client := range cm.connections {
        client.Close()
    }
}

func partitionProducts(products []string, size int) [][]string {
    var groups [][]string
    for i := 0; i < len(products); i += size {
        end := i + size
        if end > len(products) {
            end = len(products)
        }
        groups = append(groups, products[i:end])
    }
    return groups
}
```

### WebSocket Client with Backpressure

```go
// internal/coinbase/client.go
type WebSocketClient struct {
    products    []string
    auth        *Auth
    conn        *websocket.Conn
    output      chan<- *models.Candle

    // Per-connection buffer for backpressure isolation
    localBuffer chan []byte

    // Health tracking
    lastMessage atomic.Int64
    reconnects  atomic.Int64

    ctx    context.Context
    cancel context.CancelFunc
}

func (c *WebSocketClient) readLoop() {
    const BlockTimeout = 10 * time.Millisecond

    for {
        select {
        case <-c.ctx.Done():
            return
        default:
        }

        _, msg, err := c.conn.Read(c.ctx)
        if err != nil {
            c.handleDisconnect(err)
            return
        }

        c.lastMessage.Store(time.Now().UnixMilli())

        // Non-blocking send to local buffer
        select {
        case c.localBuffer <- msg:
            // Delivered
        default:
            // Buffer full - drop message, increment counter
            metrics.DroppedMessages.WithLabelValues("websocket").Inc()
        }
    }
}

func (c *WebSocketClient) processLoop() {
    for msg := range c.localBuffer {
        candle, err := parseMessage(msg)
        if err != nil {
            continue
        }

        // Non-blocking send to output with timeout
        select {
        case c.output <- candle:
            // Delivered
        case <-time.After(10 * time.Millisecond):
            // Global backpressure - log and drop
            metrics.DroppedMessages.WithLabelValues("output").Inc()
        case <-c.ctx.Done():
            return
        }
    }
}
```

## Sharded Aggregator

Replaces the single-goroutine aggregator bottleneck with a 16-shard parallel aggregator. Uses FNV-1a hashing for consistent product-to-shard routing.

### Why Sharding?

- **Single goroutine is a bottleneck**: At 500 products with 8 granularities, processing 4000 updates/minute on one goroutine limits throughput
- **Lock-free routing**: FNV-1a hash determines shard without coordination
- **Horizontal scalability**: Each shard processes independently

### Implementation

```go
// internal/aggregator/sharded_aggregator.go
package aggregator

import (
    "sync"

    "spot-canvas-app/internal/models"
)

const NumShards = 16  // Power of 2 for fast modulo

type ShardedAggregator struct {
    shards     [NumShards]*AggregatorShard
    outputChan chan *models.CandleUpdate
    wg         sync.WaitGroup
}

type AggregatorShard struct {
    id        int
    inputChan chan *models.Candle
    state     map[string]*candleState  // key: product+granularity+timestamp
    output    chan<- *models.CandleUpdate
}

type candleState struct {
    candle    *models.Candle
    startTime int64
}

func NewShardedAggregator(outputSize int) *ShardedAggregator {
    sa := &ShardedAggregator{
        outputChan: make(chan *models.CandleUpdate, outputSize),
    }

    for i := 0; i < NumShards; i++ {
        sa.shards[i] = &AggregatorShard{
            id:        i,
            inputChan: make(chan *models.Candle, 256),  // Per-shard buffer
            state:     make(map[string]*candleState),
            output:    sa.outputChan,
        }
        sa.wg.Add(1)
        go sa.shards[i].run(&sa.wg)
    }

    return sa
}

// Route sends a candle to the appropriate shard based on product ID hash
func (sa *ShardedAggregator) Route(candle *models.Candle) {
    shard := fnv1aHash(candle.ProductID) & (NumShards - 1)

    select {
    case sa.shards[shard].inputChan <- candle:
        // Delivered
    default:
        // Shard buffer full - drop and record
        metrics.DroppedMessages.WithLabelValues("aggregator").Inc()
    }
}

// Output returns the channel of aggregated candle updates
func (sa *ShardedAggregator) Output() <-chan *models.CandleUpdate {
    return sa.outputChan
}

func (s *AggregatorShard) run(wg *sync.WaitGroup) {
    defer wg.Done()

    for candle := range s.inputChan {
        updates := s.aggregate(candle)
        for _, update := range updates {
            select {
            case s.output <- update:
                // Delivered
            default:
                // Output channel full
                metrics.DroppedMessages.WithLabelValues("aggregator_output").Inc()
            }
        }
    }
}

func (s *AggregatorShard) aggregate(candle *models.Candle) []*models.CandleUpdate {
    var updates []*models.CandleUpdate

    for _, granularity := range models.AllGranularities {
        intervalStart := alignToInterval(candle.Timestamp, granularity)
        key := fmt.Sprintf("%s.%s.%d", candle.ProductID, granularity, intervalStart.Unix())

        state, exists := s.state[key]
        if !exists {
            // New interval
            state = &candleState{
                candle: &models.Candle{
                    Exchange:    candle.Exchange,
                    ProductID:   candle.ProductID,
                    Granularity: granularity,
                    Timestamp:   intervalStart,
                    Open:        candle.Open,
                    High:        candle.High,
                    Low:         candle.Low,
                    Close:       candle.Close,
                    Volume:      candle.Volume,
                },
                startTime: intervalStart.Unix(),
            }
            s.state[key] = state
        } else {
            // Update existing
            state.candle.High = max(state.candle.High, candle.High)
            state.candle.Low = min(state.candle.Low, candle.Low)
            state.candle.Close = candle.Close
            state.candle.Volume += candle.Volume
        }
        state.candle.LastUpdate = time.Now()

        // Check if interval is complete
        isComplete := time.Now().Unix() >= intervalStart.Unix()+int64(granularity.Seconds())

        updates = append(updates, &models.CandleUpdate{
            Candle:     state.candle,
            IsComplete: isComplete,
        })

        // Cleanup completed intervals
        if isComplete {
            delete(s.state, key)
        }
    }

    return updates
}

// fnv1aHash provides fast string hashing for shard routing
func fnv1aHash(s string) uint32 {
    h := uint32(2166136261)
    for i := 0; i < len(s); i++ {
        h ^= uint32(s[i])
        h *= 16777619
    }
    return h
}

func alignToInterval(t time.Time, g models.Granularity) time.Time {
    unix := t.Unix()
    aligned := unix - (unix % int64(g.Seconds()))
    return time.Unix(aligned, 0)
}
```

## Backpressure System

Monitors channel utilization and triggers adaptive responses when the system is overloaded.

### Backpressure Detection

```go
// internal/metrics/backpressure.go
package metrics

import (
    "sync"
    "sync/atomic"

    "github.com/prometheus/client_golang/prometheus"
)

const HighWaterMark = 0.80  // 80% utilization triggers warning

type BackpressureMonitor struct {
    channels map[string]*ChannelMetrics
    mu       sync.RWMutex
}

type ChannelMetrics struct {
    name        string
    capacity    int
    lengthFunc  func() int
    utilization prometheus.Gauge
    highWater   atomic.Int64
}

func NewBackpressureMonitor() *BackpressureMonitor {
    return &BackpressureMonitor{
        channels: make(map[string]*ChannelMetrics),
    }
}

func (bm *BackpressureMonitor) RegisterChannel(name string, capacity int, lenFunc func() int) {
    bm.mu.Lock()
    defer bm.mu.Unlock()

    bm.channels[name] = &ChannelMetrics{
        name:       name,
        capacity:   capacity,
        lengthFunc: lenFunc,
        utilization: prometheus.NewGauge(prometheus.GaugeOpts{
            Name:        "channel_utilization_ratio",
            ConstLabels: prometheus.Labels{"channel": name},
        }),
    }
    prometheus.MustRegister(bm.channels[name].utilization)
}

type BackpressureStatus struct {
    Channels     map[string]float64
    HighPressure bool
}

func (bm *BackpressureMonitor) Check() BackpressureStatus {
    bm.mu.RLock()
    defer bm.mu.RUnlock()

    status := BackpressureStatus{
        Channels: make(map[string]float64),
    }

    for name, cm := range bm.channels {
        length := cm.lengthFunc()
        utilization := float64(length) / float64(cm.capacity)
        cm.utilization.Set(utilization)
        status.Channels[name] = utilization

        if utilization > HighWaterMark {
            status.HighPressure = true
            cm.highWater.Add(1)
        }
    }

    return status
}
```

### Metrics Definition

```go
// internal/metrics/metrics.go
package metrics

import "github.com/prometheus/client_golang/prometheus"

var (
    // Throughput metrics
    CandlesReceived = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "candles_received_total",
            Help: "Total candles received from WebSocket",
        },
        []string{"product"},
    )

    CandlesProcessed = prometheus.NewCounter(prometheus.CounterOpts{
        Name: "candles_processed_total",
        Help: "Total candles processed by aggregator",
    })

    DatabaseBatchesWritten = prometheus.NewCounter(prometheus.CounterOpts{
        Name: "database_batches_written_total",
        Help: "Total database batches written",
    })

    // Latency metrics
    ProcessingLatency = prometheus.NewHistogram(prometheus.HistogramOpts{
        Name:    "candle_processing_latency_seconds",
        Help:    "Time from WebSocket receive to NATS publish",
        Buckets: []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1},
    })

    DatabaseWriteLatency = prometheus.NewHistogram(prometheus.HistogramOpts{
        Name:    "database_write_latency_seconds",
        Help:    "Time to write a batch to database",
        Buckets: []float64{0.01, 0.025, 0.05, 0.1, 0.25, 0.5},
    })

    // Backpressure metrics
    DroppedMessages = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "dropped_messages_total",
            Help: "Messages dropped due to backpressure",
        },
        []string{"stage"},  // websocket, output, aggregator, aggregator_output
    )

    // Connection health
    WebSocketConnections = prometheus.NewGauge(prometheus.GaugeOpts{
        Name: "websocket_connections_active",
        Help: "Number of active WebSocket connections",
    })

    WebSocketReconnects = prometheus.NewCounter(prometheus.CounterOpts{
        Name: "websocket_reconnects_total",
        Help: "Total WebSocket reconnection attempts",
    })
)

func init() {
    prometheus.MustRegister(
        CandlesReceived,
        CandlesProcessed,
        DatabaseBatchesWritten,
        ProcessingLatency,
        DatabaseWriteLatency,
        DroppedMessages,
        WebSocketConnections,
        WebSocketReconnects,
    )
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

Uses the sharded architecture for high-throughput candle processing.

```go
// cmd/server/main.go
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

    // Initialize backpressure monitor
    bpMonitor := metrics.NewBackpressureMonitor()

    // Initialize components with performance-tuned settings
    db := storage.NewPostgresRepository(cfg.DatabaseURL)
    writer := storage.NewBatchWriter(db, 100, 50*time.Millisecond)  // Latency-optimized
    publisher := natspkg.NewPublisher(nc)
    kvUpdater := natspkg.NewKVUpdater(kv, 10*time.Millisecond)     // 10ms dedupe

    // Sharded aggregator (16 shards)
    aggregator := aggregator.NewShardedAggregator(1000)

    // Connection manager (20 products per connection)
    connManager := coinbase.NewConnectionManager(2000)

    // Register channels for backpressure monitoring
    bpMonitor.RegisterChannel("raw_candles", 2000, func() int {
        return len(connManager.Output())
    })
    bpMonitor.RegisterChannel("aggregator_output", 1000, func() int {
        return len(aggregator.Output())
    })

    var wg sync.WaitGroup

    // Start connection manager with sharded products
    products := getShardedProducts(cfg.ShardIndex, cfg.ShardCount)
    auth := coinbase.NewAuth(cfg.CoinbaseAPIKey, cfg.CoinbasePrivateKey)
    if err := connManager.Start(products, auth); err != nil {
        log.Fatal().Err(err).Msg("failed to start connection manager")
    }

    // Pipeline: Connection Manager → Sharded Aggregator
    wg.Add(1)
    go func() {
        defer wg.Done()
        for candle := range connManager.Output() {
            aggregator.Route(candle)
        }
    }()

    // Pipeline: Sharded Aggregator → NATS + PostgreSQL
    wg.Add(1)
    go func() {
        defer wg.Done()
        for update := range aggregator.Output() {
            // Publish to NATS immediately (low latency)
            publisher.Publish(update)

            // Update KV with deduplication
            kvUpdater.Update(update)

            // Write to PostgreSQL (batched for throughput)
            writer.Add(update.Candle)
        }
    }()

    // Backpressure monitoring goroutine
    wg.Add(1)
    go func() {
        defer wg.Done()
        ticker := time.NewTicker(time.Second)
        defer ticker.Stop()
        for {
            select {
            case <-ctx.Done():
                return
            case <-ticker.C:
                status := bpMonitor.Check()
                if status.HighPressure {
                    log.Warn().Interface("channels", status.Channels).
                        Msg("high backpressure detected")
                }
            }
        }
    }()

    // Start HTTP server with NATS connection
    wg.Add(1)
    go func() {
        defer wg.Done()
        handlers.StartServer(ctx, cfg.Port, nc, kv, db)
    }()

    // Wait for shutdown
    <-sigChan
    log.Info().Msg("shutting down...")
    cancel()

    // Graceful shutdown
    connManager.Close()
    writer.Close()
    kvUpdater.Close()

    wg.Wait()
    log.Info().Msg("shutdown complete")
}
```

## Batch Writer

Optimized for low latency with smaller batches (100 rows, 50ms flush).

```go
// internal/storage/batch_writer.go
package storage

import (
    "context"
    "sync"
    "time"

    "spot-canvas-app/internal/metrics"
    "spot-canvas-app/internal/models"
)

// Latency-optimized batch settings
const (
    DefaultBatchSize     = 100              // Smaller batches for lower latency
    DefaultFlushInterval = 50 * time.Millisecond
)

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

    start := time.Now()
    err := w.repo.UpsertLiveCandleBatch(w.ctx, candles)

    // Record metrics
    metrics.DatabaseWriteLatency.Observe(time.Since(start).Seconds())
    metrics.DatabaseBatchesWritten.Inc()

    if err != nil {
        log.Error().Err(err).Int("batch_size", len(candles)).Msg("batch write failed")
    }
}

func (w *BatchWriter) Close() {
    w.cancel()
    w.wg.Wait()
}
```

### NATS KV Updater with Deduplication

```go
// internal/nats/kv_updater.go
package nats

import (
    "encoding/json"
    "fmt"
    "sync"
    "time"

    "github.com/nats-io/nats.go"
    "spot-canvas-app/internal/models"
)

// KVUpdater deduplicates updates within a time window
type KVUpdater struct {
    kv            nats.KeyValue
    pending       map[string]*models.CandleUpdate
    mu            sync.Mutex
    flushInterval time.Duration
    ctx           context.Context
    cancel        context.CancelFunc
    wg            sync.WaitGroup
}

func NewKVUpdater(kv nats.KeyValue, flushInterval time.Duration) *KVUpdater {
    ctx, cancel := context.WithCancel(context.Background())
    u := &KVUpdater{
        kv:            kv,
        pending:       make(map[string]*models.CandleUpdate),
        flushInterval: flushInterval,
        ctx:           ctx,
        cancel:        cancel,
    }
    u.wg.Add(1)
    go u.runFlushLoop()
    return u
}

func (u *KVUpdater) Update(update *models.CandleUpdate) {
    key := fmt.Sprintf("%s.%s",
        update.Candle.ProductID,
        update.Candle.Granularity.String())

    u.mu.Lock()
    u.pending[key] = update  // Keep only latest update per key
    u.mu.Unlock()
}

func (u *KVUpdater) runFlushLoop() {
    defer u.wg.Done()
    ticker := time.NewTicker(u.flushInterval)
    defer ticker.Stop()

    for {
        select {
        case <-u.ctx.Done():
            u.flush()
            return
        case <-ticker.C:
            u.flush()
        }
    }
}

func (u *KVUpdater) flush() {
    u.mu.Lock()
    if len(u.pending) == 0 {
        u.mu.Unlock()
        return
    }
    toFlush := u.pending
    u.pending = make(map[string]*models.CandleUpdate)
    u.mu.Unlock()

    for key, update := range toFlush {
        data, _ := json.Marshal(update.Candle)
        if _, err := u.kv.Put(key, data); err != nil {
            log.Error().Err(err).Str("key", key).Msg("KV put failed")
        }
    }
}

func (u *KVUpdater) Close() {
    u.cancel()
    u.wg.Wait()
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

    // Metrics & Monitoring
    github.com/prometheus/client_golang v1.x.x

    // Logging
    github.com/rs/zerolog v1.x.x

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
