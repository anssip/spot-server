from dataclasses import dataclass
from typing import List


@dataclass
class Candle:
    open: float
    high: float
    low: float
    close: float
    volume: float
    first_timestamp: int
    last_timestamp: int

    def to_list(self) -> List:
        """Convert to list format for Firestore storage"""
        return [
            self.first_timestamp,
            self.low,
            self.high,
            self.open,
            self.close,
            self.volume
        ]

    @classmethod
    def from_coinbase_message(cls, candle: dict) -> 'Candle':
        """Create Candle from Coinbase WebSocket message"""
        timestamp = int(candle['start'])
        return cls(
            open=float(candle['open']),
            high=float(candle['high']),
            low=float(candle['low']),
            close=float(candle['close']),
            volume=float(candle['volume']),
            first_timestamp=timestamp,
            last_timestamp=timestamp
        )
