## ADDED Requirements

### Requirement: Real-time Candle Ingestion

The system SHALL connect to Coinbase WebSocket API and receive real-time candle data for configured trading pairs.

#### Scenario: WebSocket connection established
- **GIVEN** valid Coinbase API credentials
- **WHEN** the server starts
- **THEN** WebSocket connections are established to Coinbase Advanced Trade API
- **AND** candle subscriptions are created for configured products

#### Scenario: Candle data received
- **WHEN** Coinbase sends a candle update message
- **THEN** the system parses the message and extracts OHLCV data
- **AND** the candle is passed to the aggregator

### Requirement: Multi-timeframe Candle Aggregation

The system SHALL aggregate 1-minute candles into multiple timeframes: 1m, 5m, 15m, 30m, 1h, 2h, 6h, 1d.

#### Scenario: Candle aggregation
- **GIVEN** a 1-minute candle is received
- **WHEN** the aggregator processes the candle
- **THEN** all 8 timeframe candles are updated with correct OHLCV values
- **AND** completed candles are marked as complete when interval boundary is crossed

#### Scenario: Memory cleanup
- **WHEN** a candle interval is completed
- **THEN** the completed candle is removed from in-memory state to prevent memory leaks

### Requirement: NATS Pub/Sub Distribution

The system SHALL publish candle updates to NATS subjects for real-time distribution to SSE handlers.

#### Scenario: Candle published to NATS
- **GIVEN** an aggregated candle update
- **WHEN** the publisher processes the update
- **THEN** the candle is published to subject `candles.{product}.{granularity}`
- **AND** the current candle state is stored in NATS KV bucket `live-candles`

#### Scenario: SSE handler subscribes to NATS
- **GIVEN** a client connects to the SSE endpoint
- **WHEN** the handler parses subscription parameters
- **THEN** NATS subscriptions are created for requested products and granularities
- **AND** initial candle state is sent from KV bucket

### Requirement: SSE Streaming (Phase 1)

The system SHALL stream candle updates to web clients using Server-Sent Events.

#### Scenario: SSE connection established
- **GIVEN** a client requests `/stream?products=BTC-USD&granularities=ONE_MINUTE`
- **WHEN** the connection is established
- **THEN** initial candle state is sent as JSON events
- **AND** subsequent updates are streamed as JSON candle events

#### Scenario: Candle event format
- **WHEN** a candle update is received from NATS
- **THEN** a JSON object containing product_id, granularity, OHLCV data, and is_complete flag is sent
- **AND** the event type is "candle"

### Requirement: Chart SSE Morphing (Phase 2 - Deferred)

In Phase 2, the system SHALL stream complete chart state via Datastar MergeFragments.

#### Scenario: Chart morphing (Phase 2)
- **GIVEN** Phase 2 implementation
- **WHEN** a client connects for chart data
- **THEN** the server renders full chart HTML (historical + live candles)
- **AND** sends it via Datastar MergeFragments for DOM morphing

### Requirement: PostgreSQL Persistence

The system SHALL persist candle data to PostgreSQL with TimescaleDB for historical queries.

#### Scenario: Candle written to database
- **GIVEN** an aggregated candle update
- **WHEN** the batch writer processes the update
- **THEN** the candle is upserted to the `live_candles` hypertable
- **AND** writes are batched for efficiency (50 items or 100ms interval)

### Requirement: Product Sharding

The system SHALL support horizontal scaling through product sharding.

#### Scenario: Products partitioned by shard
- **GIVEN** SHARD_INDEX=0 and SHARD_COUNT=3
- **WHEN** the server starts
- **THEN** only products assigned to shard 0 are processed
- **AND** each product is handled by exactly one shard

### Requirement: Health Monitoring

The system SHALL expose a health endpoint for Cloud Run monitoring.

#### Scenario: Health check success
- **GIVEN** NATS server is running and database is connected
- **WHEN** GET /health is called
- **THEN** HTTP 200 is returned with connection status
