"""CSRF token management for the bus (SilverRail) endpoints.

Tokens are scoped to the page that issued them: route pages and stop pages
issue different tokens, sent with different ModuleId/TabId headers. Using
the wrong one returns HTTP 401. Train endpoints need no token.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

import aiohttp

from .const import BASE_URL, USER_AGENT
from .exceptions import AuthError, NetworkError

_TOKEN_RE = re.compile(
    r'<input\s+name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"'
)


class AuthContext(Enum):
    ROUTE = "route"
    STOP = "stop"


@dataclass(frozen=True)
class _ContextSpec:
    module_id: str
    tab_id: str
    page_url: str  # str.format template taking ref=


_SPECS: dict[AuthContext, _ContextSpec] = {
    AuthContext.ROUTE: _ContextSpec(
        "5345", "133", BASE_URL + "/timetables/details?Bus={ref}"
    ),
    AuthContext.STOP: _ContextSpec(
        "5310",
        "141",
        BASE_URL + "/Journey-Planner/Stops-Near-You?locationtype=stop&location={ref}",
    ),
}


def bus_headers(context: AuthContext, token: str, ref: str) -> dict[str, str]:
    """Request headers for a SilverRail API call in the given auth context."""
    spec = _SPECS[context]
    headers = {
        "RequestVerificationToken": token,
        "ModuleId": spec.module_id,
        "TabId": spec.tab_id,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    }
    if context is AuthContext.STOP:
        headers["Referer"] = spec.page_url.format(ref=ref)
        headers["Origin"] = BASE_URL
    return headers


class TokenManager:
    """Caches one token per auth context; refetches after invalidate()."""

    def __init__(self) -> None:
        self._tokens: dict[AuthContext, str] = {}

    async def get_token(
        self,
        session: aiohttp.ClientSession,
        context: AuthContext,
        ref: str,
        timeout: aiohttp.ClientTimeout,
    ) -> str:
        if context in self._tokens:
            return self._tokens[context]
        url = _SPECS[context].page_url.format(ref=ref)
        try:
            async with session.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=timeout
            ) as resp:
                if resp.status != 200:
                    raise AuthError(f"Token page returned HTTP {resp.status}")
                html = await resp.text()
        except aiohttp.ClientError as err:
            raise NetworkError(f"Could not reach Transperth: {err}") from err
        match = _TOKEN_RE.search(html)
        if not match:
            raise AuthError(f"No verification token found on {url}")
        self._tokens[context] = match.group(1)
        return self._tokens[context]

    def invalidate(self, context: AuthContext) -> None:
        self._tokens.pop(context, None)
