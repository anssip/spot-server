from datetime import datetime, timedelta
from typing import Dict, Optional, List
from coinbase.rest import RESTClient
from .models import Candle, Granularity

class CoinbasePriceDataService:
    MAX_CANDLES_PER_REQUEST = 300

    def __init__(self, api_key: str, api_secret: str, client: Optional[RESTClient] = None):
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.client = client or RESTClient(api_key=api_key, api_secret=api_secret)

    def _fetch_candle_page(self, symbol: str, granularity: Granularity, start: datetime, end: datetime) -> Dict[int, Candle]:
        """Fetch a single page of candles"""
        response = self.client.get_candles(
            product_id=symbol,
            granularity=granularity.name,
            start=str(int(start.timestamp())),
            end=str(int(end.timestamp()))
        )
        
        return self._transform_data(response["candles"], granularity)

    async def fetch_candles(
        self, 
        symbol: str = "BTC-USD",
        granularity: Granularity = Granularity.ONE_HOUR,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> Dict[int, Candle]:
        """Fetch candles with pagination if needed"""
        if not end:
            end = datetime.now()
        if not start:
            start = end - timedelta(days=1)

        # Calculate time delta for one candle based on granularity
        seconds_per_candle = granularity.seconds  # Use the seconds property
        total_seconds = int((end - start).total_seconds())
        total_candles = total_seconds // seconds_per_candle

        if total_candles <= self.MAX_CANDLES_PER_REQUEST:
            # Single request is sufficient
            return self._fetch_candle_page(symbol, granularity, start, end)

        # Multiple requests needed
        all_candles = {}
        current_start = start
        
        while current_start < end:
            # Calculate end time for this batch
            batch_end = min(
                current_start + timedelta(seconds=seconds_per_candle * self.MAX_CANDLES_PER_REQUEST),
                end
            )

            try:
                batch_candles = self._fetch_candle_page(
                    symbol, 
                    granularity,
                    current_start,
                    batch_end
                )
                all_candles.update(batch_candles)
                
                # Move to next batch
                current_start = batch_end
                
            except Exception as e:
                raise Exception(f"Error fetching candles batch {current_start} - {batch_end}: {str(e)}")

        return all_candles

    def _transform_data(self, candles: List[dict], granularity: Granularity) -> Dict[int, Candle]:
        """Transform Coinbase candle data to our Candle model
        
        Coinbase Advanced Trade API returns candles in this format:
        {
            "start": "1736708400",  # Unix timestamp in seconds
            "low": "40000.0",
            "high": "41000.0",
            "open": "40500.0",
            "close": "40800.0",
            "volume": "100.0"
        }
        """
        result = {}
        for candle_data in candles:
            # Convert string timestamp to int
            timestamp = int(candle_data["start"])
            candle = Candle(
                open=float(candle_data["open"]),
                high=float(candle_data["high"]),
                low=float(candle_data["low"]),
                close=float(candle_data["close"]),
                volume=float(candle_data["volume"]),
                first_timestamp=timestamp,
                last_timestamp=timestamp
            )
            result[timestamp * 1000] = candle
        return result 