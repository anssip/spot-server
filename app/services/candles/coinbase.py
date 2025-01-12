import time
from datetime import datetime, timedelta
from typing import Dict, Optional
import hmac
import hashlib
import base64
import json
import aiohttp
import asyncio
from .models import Candle, Granularity

class CoinbasePriceDataService:
    MAX_CANDLES_PER_REQUEST = 300

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.base_url = "https://api.coinbase.com/api/v3/brokerage"

    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        message = timestamp + method + request_path + body
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(signature.digest()).decode('utf-8')

    async def _fetch_candle_page(self, symbol: str, granularity: Granularity, start: datetime, end: datetime) -> Dict[int, Candle]:
        """Fetch a single page of candles"""
        endpoint = f"/products/{symbol}/candles"
        params = {
            "granularity": granularity.value,
            "start": str(int(start.timestamp())),
            "end": str(int(end.timestamp()))
        }

        timestamp = str(int(time.time()))
        signature = self._generate_signature(timestamp, "GET", endpoint)
        headers = {
            "CB-ACCESS-KEY": self.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=headers
            ) as response:
                if response.status != 200:
                    error_data = await response.json()
                    raise Exception(f"Coinbase API error: {error_data}")
                
                data = await response.json()
                return self._transform_data(data["candles"], granularity)

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
        seconds_per_candle = int(granularity.seconds)
        total_seconds = int((end - start).total_seconds())
        total_candles = total_seconds // seconds_per_candle

        if total_candles <= self.MAX_CANDLES_PER_REQUEST:
            # Single request is sufficient
            return await self._fetch_candle_page(symbol, granularity, start, end)

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
                batch_candles = await self._fetch_candle_page(
                    symbol, 
                    granularity,
                    current_start,
                    batch_end
                )
                all_candles.update(batch_candles)
                
                # Move to next batch
                current_start = batch_end
                
                # Small delay between requests
                await asyncio.sleep(0.2)
                
            except Exception as e:
                raise Exception(f"Error fetching candles batch {current_start} - {batch_end}: {str(e)}")

        return all_candles

    def _transform_data(self, candles: list, granularity: Granularity) -> Dict[int, Candle]:
        """Transform Coinbase candle data to our Candle model"""
        result = {}
        for candle_data in candles:
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