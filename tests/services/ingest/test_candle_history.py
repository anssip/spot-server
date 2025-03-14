import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import base64
from app.services.ingest.candle_history import CandleHistoryIngestService
from app.services.candles.coinbase import CoinbasePriceDataService
from app.services.candles.models import Granularity, Candle

@pytest.fixture
def mock_coinbase_service():
    service = MagicMock()
    service.fetch_candles = AsyncMock()
    return service

@pytest.fixture
def mock_db():
    db = MagicMock()
    # Create a batch with async commit
    batch = MagicMock()
    batch.commit = MagicMock()
    db.batch.return_value = batch
    
    # Create collection and document mocks
    doc_mock = MagicMock()
    doc_mock.get = MagicMock()
    collection_mock = MagicMock()
    collection_mock.document.return_value = doc_mock
    collection_mock.where.return_value = collection_mock
    collection_mock.order_by.return_value = collection_mock
    db.collection.return_value = collection_mock
    
    return db

@pytest.fixture
def service(mock_db, mock_coinbase_service):
    return CandleHistoryIngestService(mock_db, mock_coinbase_service)

@pytest.mark.asyncio
async def test_ingest_history(service, mock_db, mock_coinbase_service):
    """Test ingesting historical candles"""
    # Mock Coinbase API response
    def create_candles(start_time: int, count: int):
        return {
            ts: Candle(
                open=46500.0,
                high=47000.0,
                low=46000.0,
                close=46800.0,
                volume=100.5,
                first_timestamp=ts,
                last_timestamp=ts
            )
            for ts in [int((datetime.fromtimestamp(start_time) + timedelta(hours=i)).timestamp() * 1000) for i in range(count)]
        }

    # Setup mock response
    start_time = int(datetime.now().timestamp()) - 250 * 3600
    mock_response = create_candles(start_time, 250)
    mock_coinbase_service.fetch_candles.return_value = mock_response

    # Test ingestion
    count = await service.ingest_history()
    
    # Verify we got enough candles
    assert count >= 200
    
    # Verify Firestore operations
    collection_mock = mock_db.collection.return_value
    assert collection_mock.document.called
    
    # Verify document was created with correct path
    collection_path = mock_db.collection.call_args[0][0]
    assert f"exchanges/coinbase/products/BTC-USD/history/{Granularity.ONE_HOUR.name}/candles" == collection_path
    
    # Verify batch commit was called
    batch = mock_db.batch.return_value
    assert batch.commit.called

    # Verify Coinbase service was called correctly
    call_kwargs = mock_coinbase_service.fetch_candles.call_args.kwargs
    assert call_kwargs['symbol'] == "BTC-USD"
    assert call_kwargs['granularity'] == Granularity.ONE_HOUR
    assert call_kwargs['start'].replace(microsecond=0) == datetime.fromtimestamp(start_time).replace(microsecond=0)
    assert call_kwargs['end'].replace(microsecond=0) == datetime.fromtimestamp(start_time + 250 * 3600).replace(microsecond=0)

@pytest.mark.asyncio
async def test_get_candles(service, mock_db):
    """Test retrieving candles for a time range"""
    # Set up test data
    start = datetime(2022, 1, 1)
    end = start + timedelta(hours=48)  # 2 days of data

    # Create mock documents
    mock_docs = []
    current = start
    
    while current < end:
        ts = int(current.timestamp() * 1000)
        mock_doc = MagicMock()
        mock_doc.id = str(ts)
        mock_doc.to_dict.return_value = {
            "open": 46500.0,
            "high": 47000.0,
            "low": 46000.0,
            "close": 46800.0,
            "volume": 100.5,
            "first_timestamp": ts,
            "last_timestamp": ts
        }
        mock_docs.append(mock_doc)
        current += timedelta(hours=1)

    # Set up mock query response
    collection_mock = mock_db.collection.return_value
    collection_mock.stream = MagicMock(return_value=mock_docs)

    # Test retrieving candles
    result = await service.get_candles(
        symbol="BTC-USD",
        granularity=Granularity.ONE_HOUR,
        start=start,
        end=end
    )

    # Verify results
    assert len(result) == 48  # Should get 48 hours of data
    
    # Verify candles are continuous
    timestamps = sorted(result.keys())
    for i in range(1, len(timestamps)):
        assert timestamps[i] - timestamps[i-1] == 3600000  # 1 hour in milliseconds
    
    # Verify first and last timestamps
    assert timestamps[0] == int(start.timestamp() * 1000)
    assert timestamps[-1] == int((end - timedelta(hours=1)).timestamp() * 1000)
    
    # Verify query was constructed correctly
    collection_path = mock_db.collection.call_args[0][0]
    assert f"exchanges/coinbase/products/BTC-USD/history/{Granularity.ONE_HOUR.name}/candles" == collection_path
    
    # Verify where clauses were called
    start_ts = int(start.timestamp() * 1000)
    end_ts = int(end.timestamp() * 1000)
    collection_mock.where.assert_any_call("first_timestamp", ">=", start_ts)
    collection_mock.where.assert_any_call("first_timestamp", "<=", end_ts)
    collection_mock.order_by.assert_called_once_with("first_timestamp") 