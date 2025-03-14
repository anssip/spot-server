from datetime import datetime, timedelta
from typing import Dict
from google.cloud import firestore
from ..candles.models import Candle, Granularity
from ..candles.coinbase import CoinbasePriceDataService

class CandleHistoryIngestService:
    def __init__(self, db: firestore.Client, coinbase_service: CoinbasePriceDataService):
        self.db = db
        self.coinbase_service = coinbase_service

    async def ingest_history(self, symbol: str = "BTC-USD", granularity: Granularity = Granularity.ONE_HOUR):
        """Ingest historical candles for a given symbol and granularity"""
        # Fetch enough history for 200-period moving average
        end = datetime.now()
        # Fetch a bit more than 200 periods to ensure we have enough data
        start = end - timedelta(hours=250)

        candles = await self.coinbase_service.fetch_candles(
            symbol=symbol,
            granularity=granularity,
            start=start,
            end=end
        )
        print(f"Fetched {len(candles)} candles")

        # Store candles in batches to avoid large transactions
        await self._store_candles(symbol, granularity, candles)
        
        return len(candles)

    async def _store_candles(self, symbol: str, granularity: Granularity, candles: Dict[int, Candle]):
        """Store candles in Firestore"""
        # Base collection for history
        collection_path = f"exchanges/coinbase/products/{symbol}/history/{granularity.name}/candles"
        history_collection = self.db.collection(collection_path)
        
        # Store candles in batches
        batch = self.db.batch()
        count = 0
        
        for ts_ms, candle in candles.items():
            doc_ref = history_collection.document(str(ts_ms))
            batch.set(doc_ref, candle.to_dict(), merge=True)
            count += 1
            
            # Commit batch every 500 operations
            if count >= 500:
                batch.commit()
                batch = self.db.batch()
                count = 0
        
        # Commit any remaining operations
        if count > 0:
            batch.commit()

    async def get_candles(self, symbol: str, granularity: Granularity, start: datetime, end: datetime) -> Dict[int, Candle]:
        """Fetch candles for a given time range"""
        collection_path = f"exchanges/coinbase/products/{symbol}/history/{granularity.name}/candles"
        history_collection = self.db.collection(collection_path)
        
        # Convert timestamps to milliseconds
        start_ts = int(start.timestamp() * 1000)
        end_ts = int(end.timestamp() * 1000)
        
        # Query using timestamp field
        query = (history_collection
                .where("first_timestamp", ">=", start_ts)
                .where("first_timestamp", "<=", end_ts)
                .order_by("first_timestamp"))
        
        # Execute query and convert results to Candle objects
        candles = {}
        for doc in query.stream():
            ts = int(doc.id)  # Document ID is the timestamp
            candles[ts] = Candle.from_dict(doc.to_dict())
        
        return candles
