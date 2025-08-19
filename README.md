# Spot Server

This is the server for the Spot API. It provides to ways to fetch data:

1. An endpoint to fetch candles
2. Stores live price info to Firestore so that clients can subscribe to live updates

## TODO

Indicators to implement:

- [ ] Make it insert history numbers continuously
- [ ] MA 50&200
- [ ] RSI 14
- [ ] MACD 12, 26, 9
- [ ] Stochastic 14, 3, 3
- [ ] ATR 14
- [ ] Bollinger Bands 20, 2
- [ ]

## Installation

To install the dependencies, run `make install`.

## Development

To run the server, run `make dev`.

## Deployment

```bash
./scripts/deploy.sh
```

or

```bash
make deploy
```

# Firestore data model

```pre
firestore/
├── exchanges/
│   └── coinbase/  # Document
│       └── products/
│           └── BTC-USD/  # Document
│               ├── base_currency
│               ├── quote_currency
│               ├── status
│               ├── min_size
│               ├── max_size
│               └── last_updated
│
├── trading_pairs/
│   └── exchanges/  # Document
│       └── coinbase/  # Map field
│           └── BTC-USD/  # Map entry
│               ├── base_currency
│               ├── quote_currency
│               ├── status
│               ├── min_size
│               ├── max_size
│               └── last_updated
│
├── live_candles/
│   └── BTC-USD/  # Document
│       ├── timestamp
│       ├── open
│       ├── high
│       ├── low
│       ├── close
│       ├── volume
│       ├── lastUpdate
│       └── productId
│
└── historical_candles/
    ├── BTC-USD-1234567890/  # Document (productId-timestamp)
    │   ├── timestamp
    │   ├── open
    │   ├── high
    │   ├── low
    │   ├── close
    │   ├── volume
    │   └── productId
    └── ...
```
