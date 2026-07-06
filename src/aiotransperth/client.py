"""Async client for Transperth's unofficial website APIs."""

from __future__ import annotations

import json
from types import TracebackType
from typing import Any, Self

import aiohttp

from .auth import AuthContext, TokenManager, bus_headers
from .const import DEFAULT_TIMEOUT
from .exceptions import (
    AuthError,
    NetworkError,
    RateLimitError,
    TransperthError,
)


class TransperthClient:
    """One client for bus and train queries.

    Use as an async context manager, or pass an existing aiohttp session
    (it will not be closed for you).
    """

    def __init__(
        self,
        session: aiohttp.ClientSession | None = None,
        *,
        request_timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._session = session
        self._owns_session = session is None
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)
        self._tokens = TokenManager()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _bus_post(
        self, context: AuthContext, ref: str, url: str, data: dict[str, str]
    ) -> dict[str, Any]:
        """Token-authenticated form POST to a SilverRail endpoint."""
        session = self._ensure_session()
        for attempt in (0, 1):
            token = await self._tokens.get_token(session, context, ref, self._timeout)
            try:
                async with session.post(
                    url,
                    headers=bus_headers(context, token, ref),
                    data=data,
                    timeout=self._timeout,
                ) as resp:
                    if resp.status == 429:
                        raise RateLimitError(
                            "Transperth rate limit hit (HTTP 429); cooldown >60 s"
                        )
                    if resp.status == 401:
                        self._tokens.invalidate(context)
                        if attempt == 0:
                            continue
                        raise AuthError("Transperth rejected the token (HTTP 401)")
                    if resp.status != 200:
                        raise TransperthError(f"HTTP {resp.status} from {url}")
                    text = await resp.text()
            except aiohttp.ClientError as err:
                raise NetworkError(f"Could not reach Transperth: {err}") from err
            try:
                body: dict[str, Any] = json.loads(text)
            except json.JSONDecodeError as err:
                raise TransperthError(f"Non-JSON response from {url}") from err
            if body.get("result") != "success":
                raise TransperthError(f"API result={body.get('result')!r} from {url}")
            return body
        raise AuthError("Unreachable: 401 retry loop exhausted")  # pragma: no cover

    async def _get(self, url: str, headers: dict[str, str]) -> str:
        """Plain GET returning the body text (train endpoints, catalog page)."""
        session = self._ensure_session()
        try:
            async with session.get(
                url, headers=headers, timeout=self._timeout
            ) as resp:
                if resp.status == 429:
                    raise RateLimitError(
                        "Transperth rate limit hit (HTTP 429); cooldown >60 s"
                    )
                if resp.status != 200:
                    raise TransperthError(f"HTTP {resp.status} from {url}")
                return await resp.text()
        except aiohttp.ClientError as err:
            raise NetworkError(f"Could not reach Transperth: {err}") from err
