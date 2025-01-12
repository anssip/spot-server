from datetime import datetime, timedelta
from typing import Dict
from google.cloud import firestore
from ..candles.models import Candle, Granularity
from ..candles.coinbase import CoinbasePriceDataService

class CandleHistoryIngestService:
    # Store candles in 24-hour chunks (good balance between document size and query efficiency)
    CHUNK_SIZE_HOURS = 24

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
        collection_path = f"exchanges/coinbase/products/{symbol}/intervals/{granularity.name}/history"
        history_collection = self.db.collection(collection_path)
        
        # Group candles into chunks by timestamp
        chunks = {}
        for ts_ms, candle in candles.items():
            # Convert millisecond timestamp to chunk ID (24-hour chunks)
            chunk_id = ts_ms // (self.CHUNK_SIZE_HOURS * 3600 * 1000)
            if chunk_id not in chunks:
                chunks[chunk_id] = {}
            chunks[chunk_id][str(ts_ms)] = candle.to_dict()

        # Store each chunk in a separate document
        batch = self.db.batch()
        count = 0
        
        for chunk_id, chunk_candles in chunks.items():
            doc_ref = history_collection.document(f"chunk_{chunk_id}")
            batch.set(doc_ref, {
                "start_ts": chunk_id * self.CHUNK_SIZE_HOURS * 3600 * 1000,
                "candles": chunk_candles
            }, merge=True)
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
        collection_path = f"exchanges/coinbase/products/{symbol}/intervals/{granularity.name}/history"
        history_collection = self.db.collection(collection_path)
        
        # Calculate chunk IDs for the time range
        start_chunk = int(start.timestamp() * 1000) // (self.CHUNK_SIZE_HOURS * 3600 * 1000)
        end_chunk = int(end.timestamp() * 1000) // (self.CHUNK_SIZE_HOURS * 3600 * 1000)
        
        # Query all chunks in the range
        candles = {}
        for chunk_id in range(start_chunk, end_chunk + 1):
            doc_ref = history_collection.document(f"chunk_{chunk_id}")
            doc = doc_ref.get()
            if doc.exists:
                chunk_data = doc.to_dict()
                for ts_str, candle_data in chunk_data["candles"].items():
                    ts = int(ts_str)
                    if start.timestamp() * 1000 <= ts <= end.timestamp() * 1000:
                        candles[ts] = Candle.from_dict(candle_data)
        
        return candles
