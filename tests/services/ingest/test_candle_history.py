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
    batch.commit = AsyncMock()
    db.batch.return_value = batch
    
    # Create collection and document mocks
    doc_mock = MagicMock()
    doc_mock.get = AsyncMock()
    collection_mock = MagicMock()
    collection_mock.document.return_value = doc_mock
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
                first_timestamp=ts // 1000,
                last_timestamp=ts // 1000
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
    assert "exchanges/coinbase/products/BTC-USD/intervals/ONE_HOUR/history" == collection_path
    
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
    end = start + timedelta(hours=48)  # 2 days of data, should span 2-3 chunks

    # Create mock Firestore documents
    mock_docs = {}
    current = start
    chunk_id = int(start.timestamp() * 1000) // (service.CHUNK_SIZE_HOURS * 3600 * 1000)
    
    while current < end:
        ts = int(current.timestamp() * 1000)
        chunk = chunk_id = ts // (service.CHUNK_SIZE_HOURS * 3600 * 1000)
        
        if chunk not in mock_docs:
            mock_docs[chunk] = {
                "start_ts": chunk * service.CHUNK_SIZE_HOURS * 3600 * 1000,
                "candles": {}
            }
        
        mock_docs[chunk]["candles"][str(ts)] = {
            "open": 46500.0,
            "high": 47000.0,
            "low": 46000.0,
            "close": 46800.0,
            "volume": 100.5,
            "first_timestamp": int(current.timestamp()),
            "last_timestamp": int(current.timestamp())
        }
        
        current += timedelta(hours=1)

    # Set up mock document get response
    doc_mock = mock_db.collection.return_value.document.return_value
    
    async def mock_get():
        mock_doc = MagicMock()
        # Extract chunk_id from the last document call
        doc_path = mock_db.collection.return_value.document.call_args[0][0]
        chunk_id = int(doc_path.split("_")[-1])
        
        if chunk_id in mock_docs:
            mock_doc.exists = True
            mock_doc.to_dict = lambda: mock_docs[chunk_id]
        else:
            mock_doc.exists = False
        return mock_doc
    
    doc_mock.get = AsyncMock(side_effect=mock_get)

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
    
    # Verify document queries
    assert mock_db.collection.return_value.document.called
    # Should query 2-3 chunks for 48 hours of data
    assert 2 <= mock_db.collection.return_value.document.call_count <= 3 