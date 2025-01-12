import pytest
import re
from datetime import datetime, timedelta
from aioresponses import aioresponses
from app.services.candles.coinbase import CoinbasePriceDataService
from app.services.candles.models import Candle, Granularity

@pytest.fixture
def service():
    return CoinbasePriceDataService("test_key", "test_secret")

@pytest.fixture
def mock_response():
    return {
        "candles": [
            {
                "start": "1640995200",  # 2022-01-01 00:00:00
                "low": "46000.00",
                "high": "47000.00",
                "open": "46500.00",
                "close": "46800.00",
                "volume": "100.50"
            },
            {
                "start": "1640998800",  # 2022-01-01 01:00:00
                "low": "46200.00",
                "high": "47200.00",
                "open": "46800.00",
                "close": "47000.00",
                "volume": "120.75"
            }
        ]
    }

@pytest.mark.asyncio
async def test_fetch_single_page(service, mock_response):
    """Test fetching a single page of candles"""
    start = datetime(2022, 1, 1)
    end = datetime(2022, 1, 1, 2)  # 2 hours

    url_pattern = re.compile(f"{service.base_url}/products/BTC-USD/candles.*")
    with aioresponses() as m:
        m.get(
            url_pattern,
            status=200,
            payload=mock_response,
            repeat=True
        )

        result = await service.fetch_candles(
            symbol="BTC-USD",
            granularity=Granularity.ONE_HOUR,
            start=start,
            end=end
        )

        assert len(result) == 2
        first_candle = result[1640995200000]  # Timestamp in milliseconds
        assert isinstance(first_candle, Candle)
        assert first_candle.open == 46500.00
        assert first_candle.high == 47000.00
        assert first_candle.low == 46000.00
        assert first_candle.close == 46800.00
        assert first_candle.volume == 100.50

@pytest.mark.asyncio
async def test_error_handling(service):
    """Test error handling for API failures"""
    start = datetime(2022, 1, 1)
    end = datetime(2022, 1, 2)

    url_pattern = re.compile(f"{service.base_url}/products/BTC-USD/candles.*")
    with aioresponses() as m:
        m.get(
            url_pattern,
            status=400,
            payload={"message": "Invalid request"},
            repeat=True
        )

        with pytest.raises(Exception) as exc_info:
            await service.fetch_candles(
                symbol="BTC-USD",
                granularity=Granularity.ONE_HOUR,
                start=start,
                end=end
            )
        assert "Coinbase API error" in str(exc_info.value)

@pytest.mark.asyncio
async def test_default_parameters(service, mock_response):
    """Test that default parameters work correctly"""
    url_pattern = re.compile(f"{service.base_url}/products/BTC-USD/candles.*")
    with aioresponses() as m:
        m.get(
            url_pattern,
            status=200,
            payload=mock_response,
            repeat=True
        )

        result = await service.fetch_candles()  # Use defaults
        assert len(result) == 2 

@pytest.mark.asyncio
async def test_pagination(service):
    """Test that pagination works for large time ranges"""
    start = datetime(2022, 1, 1)
    end = start + timedelta(days=20)  # 480 hours, should require at least 2 requests

    # Calculate expected batches
    total_hours = int((end - start).total_seconds() / 3600)
    print(f"Total hours: {total_hours}")
    num_batches = (total_hours + service.MAX_CANDLES_PER_REQUEST - 1) // service.MAX_CANDLES_PER_REQUEST
    print(f"Number of batches: {num_batches}")
    assert num_batches > 1

    class RequestCounter:
        def __init__(self):
            self.count = 0

    counter = RequestCounter()

    def count_request(*args, **kwargs):
        counter.count += 1
        return None  # Return None to use the original response configuration

    url_pattern = re.compile(f"{service.base_url}/products/BTC-USD/candles.*")
    with aioresponses() as m:
        # Add responses for each batch
        for batch in range(num_batches):
            start_idx = batch * service.MAX_CANDLES_PER_REQUEST
            remaining_hours = total_hours - start_idx
            candles_in_batch = min(service.MAX_CANDLES_PER_REQUEST, remaining_hours)
            
            batch_start_time = int(start.timestamp()) + start_idx * 3600
            m.get(
                url_pattern,
                status=200,
                payload={
                    "candles": [
                        {
                            "start": str(batch_start_time + i * 3600),
                            "low": "46000.00",
                            "high": "47000.00",
                            "open": "46500.00",
                            "close": "46800.00",
                            "volume": "100.50"
                        }
                        for i in range(candles_in_batch)
                    ]
                },
                callback=count_request
            )

        result = await service.fetch_candles(
            symbol="BTC-USD",
            granularity=Granularity.ONE_HOUR,
            start=start,
            end=end
        )

        print(f"Actual API requests made: {counter.count}")

        # Verify total number of candles
        assert len(result) == total_hours
        assert counter.count == num_batches  # Verify the number of API requests matches expected batches

        # Verify candles are continuous
        timestamps = sorted(result.keys())
        for i in range(1, len(timestamps)):
            assert timestamps[i] - timestamps[i-1] == 3600000  # 1 hour in milliseconds

        # Verify first and last timestamps
        first_ts = int(start.timestamp()) * 1000
        last_ts = int((end - timedelta(hours=1)).timestamp()) * 1000
        assert timestamps[0] == first_ts
        assert timestamps[-1] == last_ts 