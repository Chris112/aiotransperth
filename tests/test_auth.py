import aiohttp
import pytest
from aioresponses import aioresponses

from aiotransperth.auth import AuthContext, TokenManager, bus_headers
from aiotransperth.exceptions import AuthError, NetworkError

TOKEN_HTML = (
    '<input name="__RequestVerificationToken" type="hidden" value="tok123" />'
)
STOP_PAGE = (
    "https://www.transperth.wa.gov.au/Journey-Planner/Stops-Near-You"
    "?locationtype=stop&location=12627"
)
TIMEOUT = aiohttp.ClientTimeout(total=15)


async def test_get_token_and_cache() -> None:
    manager = TokenManager()
    with aioresponses() as mock:
        mock.get(STOP_PAGE, body=TOKEN_HTML)  # registered once: cache must hold
        async with aiohttp.ClientSession() as session:
            t1 = await manager.get_token(session, AuthContext.STOP, "12627", TIMEOUT)
            t2 = await manager.get_token(session, AuthContext.STOP, "12627", TIMEOUT)
    assert t1 == t2 == "tok123"


async def test_invalidate_forces_refetch() -> None:
    manager = TokenManager()
    with aioresponses() as mock:
        mock.get(STOP_PAGE, body=TOKEN_HTML)
        mock.get(STOP_PAGE, body=TOKEN_HTML.replace("tok123", "tok456"))
        async with aiohttp.ClientSession() as session:
            t1 = await manager.get_token(session, AuthContext.STOP, "12627", TIMEOUT)
            manager.invalidate(AuthContext.STOP)
            t2 = await manager.get_token(session, AuthContext.STOP, "12627", TIMEOUT)
    assert (t1, t2) == ("tok123", "tok456")


async def test_missing_token_raises_auth_error() -> None:
    manager = TokenManager()
    with aioresponses() as mock:
        mock.get(STOP_PAGE, body="<html>no token here</html>")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(AuthError):
                await manager.get_token(session, AuthContext.STOP, "12627", TIMEOUT)


async def test_non_200_raises_auth_error() -> None:
    manager = TokenManager()
    with aioresponses() as mock:
        mock.get(STOP_PAGE, status=503)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(AuthError):
                await manager.get_token(session, AuthContext.STOP, "12627", TIMEOUT)


async def test_connection_error_raises_network_error() -> None:
    manager = TokenManager()
    with aioresponses() as mock:
        mock.get(STOP_PAGE, exception=aiohttp.ClientConnectionError("boom"))
        async with aiohttp.ClientSession() as session:
            with pytest.raises(NetworkError):
                await manager.get_token(session, AuthContext.STOP, "12627", TIMEOUT)


def test_bus_headers_stop_context_has_referer() -> None:
    headers = bus_headers(AuthContext.STOP, "tok", "12627")
    assert headers["RequestVerificationToken"] == "tok"
    assert headers["ModuleId"] == "5310" and headers["TabId"] == "141"
    assert headers["Referer"] == STOP_PAGE
    route = bus_headers(AuthContext.ROUTE, "tok", "414")
    assert route["ModuleId"] == "5345" and "Referer" not in route
