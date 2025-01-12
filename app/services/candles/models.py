from dataclasses import dataclass
from typing import List
from enum import Enum


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

class Granularity(str, Enum):
    ONE_MINUTE = "ONE_MINUTE"
    FIVE_MINUTE = "FIVE_MINUTE"
    FIFTEEN_MINUTE = "FIFTEEN_MINUTE"
    THIRTY_MINUTE = "THIRTY_MINUTE"
    ONE_HOUR = "ONE_HOUR"
    TWO_HOUR = "TWO_HOUR"
    SIX_HOUR = "SIX_HOUR"
    ONE_DAY = "ONE_DAY"

    @property
    def seconds(self) -> int:
        """Get interval length in seconds"""
        mapping = {
            "ONE_MINUTE": 60,
            "FIVE_MINUTE": 300,
            "FIFTEEN_MINUTE": 900,
            "THIRTY_MINUTE": 1800,
            "ONE_HOUR": 3600,
            "TWO_HOUR": 7200,
            "SIX_HOUR": 21600,
            "ONE_DAY": 86400
        }
        return mapping[self.value]

__all__ = ['Candle', 'Granularity']
