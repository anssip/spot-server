# Spot Server

This is the server for the Spot API.

## Installation

To install the dependencies, run `make install`.

## Development

To run the server, run `make dev`.

## Deployment

```bash
./scripts/deploy.sh
```


# Firestore data model

```pre
firestore/
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