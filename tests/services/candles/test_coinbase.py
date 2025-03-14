import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from app.services.candles.coinbase import CoinbasePriceDataService
from app.services.candles.models import Granularity, Candle

@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_candles = MagicMock()
    return client

@pytest.fixture
def service(mock_client):
    return CoinbasePriceDataService("test_key", "test_secret", client=mock_client)

@pytest.mark.asyncio
async def test_fetch_single_page(service, mock_client):
    """Test fetching a single page of candles"""
    # Setup test data
    start = datetime(2024, 1, 1)
    end = start + timedelta(hours=1)

    # Mock response
    mock_response = {
        "candles": [
            {
                "start": str(int(start.timestamp())),
                "low": "40000.0",
                "high": "41000.0",
                "open": "40500.0",
                "close": "40800.0",
                "volume": "100.0"
            }
        ]
    }
    mock_client.get_candles.return_value = mock_response

    # Test
    candles = await service.fetch_candles(
        symbol="BTC-USD",
        granularity=Granularity.ONE_HOUR,
        start=start,
        end=end
    )

    # Verify API call
    mock_client.get_candles.assert_called_once_with(
        product_id="BTC-USD",
        granularity=Granularity.ONE_HOUR.name,
        start=str(int(start.timestamp())),
        end=str(int(end.timestamp()))
    )

    # Verify results
    assert len(candles) == 1
    candle = list(candles.values())[0]
    assert isinstance(candle, Candle)
    assert candle.open == 40500.0
    assert candle.close == 40800.0

@pytest.mark.asyncio
async def test_fetch_with_pagination(service, mock_client):
    """Test fetching candles with pagination"""
    # Setup test data
    start = datetime(2024, 1, 1)
    # Request 400 candles (more than MAX_CANDLES_PER_REQUEST=300)
    end = start + timedelta(hours=400)

    # Create mock responses for each page
    mock_responses = []
    current = start
    
    # First batch: 300 candles
    first_batch = {
        "candles": [
            {
                "start": str(int((current + timedelta(hours=i)).timestamp())),
                "low": "40000.0",
                "high": "41000.0",
                "open": "40500.0",
                "close": "40800.0",
                "volume": "100.0"
            }
            for i in range(300)  # MAX_CANDLES_PER_REQUEST
        ]
    }
    mock_responses.append(first_batch)
    
    # Second batch: remaining 100 candles
    second_batch = {
        "candles": [
            {
                "start": str(int((current + timedelta(hours=300 + i)).timestamp())),
                "low": "40000.0",
                "high": "41000.0",
                "open": "40500.0",
                "close": "40800.0",
                "volume": "100.0"
            }
            for i in range(100)
        ]
    }
    mock_responses.append(second_batch)

    mock_client.get_candles = MagicMock(side_effect=mock_responses)

    # Test
    candles = await service.fetch_candles(
        symbol="BTC-USD",
        granularity=Granularity.ONE_HOUR,
        start=start,
        end=end
    )

    # Verify API calls
    calls = mock_client.get_candles.call_args_list
    assert len(calls) == 2  # Should have made exactly 2 requests

    # Verify first call (first 300 candles)
    first_call = calls[0]
    assert first_call[1]["product_id"] == "BTC-USD"
    assert first_call[1]["granularity"] == Granularity.ONE_HOUR.name
    assert first_call[1]["start"] == str(int(start.timestamp()))
    first_batch_end = start + timedelta(hours=300)
    assert first_call[1]["end"] == str(int(first_batch_end.timestamp()))

    # Verify second call (remaining 100 candles)
    second_call = calls[1]
    assert second_call[1]["product_id"] == "BTC-USD"
    assert second_call[1]["granularity"] == Granularity.ONE_HOUR.name
    assert second_call[1]["start"] == str(int(first_batch_end.timestamp()))
    assert second_call[1]["end"] == str(int(end.timestamp()))

    # Verify results
    assert len(candles) == 400  # Total number of candles
    assert all(isinstance(candle, Candle) for candle in candles.values())
    
    # Verify candles are continuous
    timestamps = sorted(candles.keys())
    for i in range(1, len(timestamps)):
        assert timestamps[i] - timestamps[i-1] == 3600000  # 1 hour in milliseconds

@pytest.mark.asyncio
async def test_api_error_handling(service, mock_client):
    """Test handling of API errors"""
    start = datetime(2024, 1, 1)
    end = start + timedelta(hours=1)

    # Mock error response
    error_message = "Coinbase API error: Invalid credentials"
    mock_client.get_candles = MagicMock(side_effect=Exception(error_message))

    # Test
    with pytest.raises(Exception) as exc_info:
        await service.fetch_candles(
            symbol="BTC-USD",
            granularity=Granularity.ONE_HOUR,
            start=start,
            end=end
        )

    # Verify the error message
    assert str(exc_info.value) == error_message 