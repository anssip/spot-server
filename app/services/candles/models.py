from dataclasses import dataclass
from enum import Enum

class Granularity(Enum):
    ONE_MINUTE = "60"
    FIVE_MINUTES = "300"
    FIFTEEN_MINUTES = "900"
    THIRTY_MINUTES = "1800"
    ONE_HOUR = "3600"
    TWO_HOURS = "7200"
    SIX_HOURS = "21600"
    ONE_DAY = "86400"

    @property
    def seconds(self) -> int:
        return int(self.value)

@dataclass
class Candle:
    open: float
    high: float
    low: float
    close: float
    volume: float
    first_timestamp: int
    last_timestamp: int

    def to_dict(self) -> dict:
        """Convert candle to dictionary for Firestore storage"""
        return {
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Candle':
        """Create Candle from dictionary (Firestore format)"""
        return cls(
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=float(data["volume"]),
            first_timestamp=int(data["first_timestamp"]),
            last_timestamp=int(data["last_timestamp"])
        )

    @classmethod
    def from_coinbase_message(cls, candle: dict) -> 'Candle':
        """Create Candle from Coinbase API response"""
        timestamp = int(candle["start"])
        return cls(
            open=float(candle["open"]),
            high=float(candle["high"]),
            low=float(candle["low"]),
            close=float(candle["close"]),
            volume=float(candle["volume"]),
            first_timestamp=timestamp,
            last_timestamp=timestamp
        )
