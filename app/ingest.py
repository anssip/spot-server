#!/usr/bin/env python3
import asyncio
import logging
from datetime import datetime, timedelta
from google.cloud import firestore
from services.candles.coinbase import CoinbasePriceDataService
from services.ingest.candle_history import CandleHistoryIngestService
from services.candles.models import Granularity
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    try:
        # Validate settings
        settings.validate_coinbase_settings()

        # Initialize services
        db = firestore.Client()
        coinbase_service = CoinbasePriceDataService(
            settings.COINBASE_API_KEY,
            settings.COINBASE_API_SECRET
        )
        history_service = CandleHistoryIngestService(db, coinbase_service)

        # Ingest historical data for BTC-USD
        logger.info("Starting historical data ingestion for BTC-USD...")
        count = await history_service.ingest_history(
            symbol="BTC-USD",
            granularity=Granularity.ONE_HOUR
        )
        logger.info(f"Successfully ingested {count} candles")

        # Verify data by fetching recent candles
        end = datetime.now()
        start = end - timedelta(hours=48)  # Fetch last 48 hours
        
        candles = await history_service.get_candles(
            symbol="BTC-USD",
            granularity=Granularity.ONE_HOUR,
            start=start,
            end=end
        )
        logger.info(f"Verification: Successfully retrieved {len(candles)} recent candles")

    except ValueError as e:
        logger.error(str(e))
        return
    except Exception as e:
        logger.error(f"Error during ingestion: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main()) 