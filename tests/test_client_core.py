import aiohttp
import pytest
from aioresponses import aioresponses

from aiotransperth.auth import AuthContext
from aiotransperth.client import TransperthClient
from aiotransperth.exceptions import (
    AuthError,
    NetworkError,
    RateLimitError,
    TransperthError,
)

STOP_PAGE = (
    "https://www.transperth.wa.gov.au/Journey-Planner/Stops-Near-You"
    "?locationtype=stop&location=12627"
)
API_URL = "https://example.invalid/api"
TOKEN_HTML = (
    '<input name="__RequestVerificationToken" type="hidden" value="tok123" />'
)


async def test_bus_post_success() -> None:
    with aioresponses() as mock:
        mock.get(STOP_PAGE, body=TOKEN_HTML)
        mock.post(API_URL, payload={"result": "success", "trips": []})
        async with TransperthClient() as client:
            body = await client._bus_post(AuthContext.STOP, "12627", API_URL, {})
    assert body["result"] == "success"


async def test_bus_post_429_raises_rate_limit() -> None:
    with aioresponses() as mock:
        mock.get(STOP_PAGE, body=TOKEN_HTML)
        mock.post(API_URL, status=429, body="Too Many Requests")
        async with TransperthClient() as client:
            with pytest.raises(RateLimitError):
                await client._bus_post(AuthContext.STOP, "12627", API_URL, {})


async def test_bus_post_401_retries_once_then_raises() -> None:
    with aioresponses() as mock:
        mock.get(STOP_PAGE, body=TOKEN_HTML)
        mock.post(API_URL, status=401)
        mock.get(STOP_PAGE, body=TOKEN_HTML)  # token refetched after invalidate
        mock.post(API_URL, status=401)
        async with TransperthClient() as client:
            with pytest.raises(AuthError):
                await client._bus_post(AuthContext.STOP, "12627", API_URL, {})


async def test_bus_post_401_then_success_recovers() -> None:
    with aioresponses() as mock:
        mock.get(STOP_PAGE, body=TOKEN_HTML)
        mock.post(API_URL, status=401)
        mock.get(STOP_PAGE, body=TOKEN_HTML)
        mock.post(API_URL, payload={"result": "success"})
        async with TransperthClient() as client:
            body = await client._bus_post(AuthContext.STOP, "12627", API_URL, {})
    assert body["result"] == "success"


async def test_bus_post_result_not_success_raises() -> None:
    with aioresponses() as mock:
        mock.get(STOP_PAGE, body=TOKEN_HTML)
        mock.post(API_URL, payload={"result": "failure"})
        async with TransperthClient() as client:
            with pytest.raises(TransperthError):
                await client._bus_post(AuthContext.STOP, "12627", API_URL, {})


async def test_bus_post_network_error() -> None:
    with aioresponses() as mock:
        mock.get(STOP_PAGE, body=TOKEN_HTML)
        mock.post(API_URL, exception=aiohttp.ClientConnectionError("boom"))
        async with TransperthClient() as client:
            with pytest.raises(NetworkError):
                await client._bus_post(AuthContext.STOP, "12627", API_URL, {})


async def test_external_session_not_closed() -> None:
    async with aiohttp.ClientSession() as session:
        client = TransperthClient(session=session)
        await client.close()
        assert not session.closed
