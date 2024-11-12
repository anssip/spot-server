from pydantic import BaseModel
from typing import Optional, List


class CandleMessage(BaseModel):
    type: str
    product_id: str
    candle: List[float]  # [start_time, low, high, open, close, volume]
    # The candle array contains:
    # [0] = start time (seconds since Unix epoch)
    # [1] = low price
    # [2] = high price
    # [3] = open price
    # [4] = close price
    # [5] = volume
