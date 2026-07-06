"""Async client for Transperth's unofficial website APIs."""

from __future__ import annotations

import json
from datetime import datetime
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import aiohttp

from .auth import AuthContext, TokenManager, bus_headers
from .const import (
    DEFAULT_TIMEOUT,
    LIVE_TRAIN_TIMES_PAGE,
    NOTE_CODES,
    OPTIONS_URL,
    STOP_TIMETABLE_URL,
    TRAIN_HEADERS,
    TRAIN_STATUS_URL_TEMPLATE,
    TRIP_URL,
    USER_AGENT,
)
from .exceptions import (
    AuthError,
    InvalidStopError,
    NetworkError,
    RateLimitError,
    TransperthError,
)
from .models import (
    PERTH_TZ,
    RouteTrip,
    Stop,
    StopTimetable,
    TrainDeparture,
    TrainStation,
    TripStop,
    parse_clock_near,
)
from .stations import parse_lines, parse_stations


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

    async def get_stop_timetable(
        self,
        stop_code: str,
        *,
        when: datetime | None = None,
        max_trips: int = 100,
    ) -> StopTimetable:
        """Upcoming departures at a bus stop, realtime included.

        The API self-caps the response window (~2 h); large max_trips is safe.
        """
        moment = when.astimezone(PERTH_TZ) if when else datetime.now(tz=PERTH_TZ)
        data = {
            "StopNumber": stop_code,
            "SearchDate": moment.strftime("%Y-%m-%d"),
            "SearchTime": moment.strftime("%H:%M"),
            "IsRealTimeChecked": "true",
            "ReturnNoteCodes": NOTE_CODES,
            "MaxTripCount": str(max_trips),
        }
        body = await self._bus_post(
            AuthContext.STOP, stop_code, STOP_TIMETABLE_URL, data
        )
        if not body.get("stop"):
            raise InvalidStopError(f"Transperth does not know stop {stop_code!r}")
        return StopTimetable.from_api(body)

    async def validate_stop(self, stop_code: str) -> Stop:
        """Check a stop code exists; return its metadata or raise InvalidStopError."""
        timetable = await self.get_stop_timetable(stop_code, max_trips=1)
        return timetable.stop

    async def get_route_trips(
        self, route: str, *, when: datetime | None = None, max_options: int = 4
    ) -> tuple[RouteTrip, ...]:
        """Upcoming trips for a bus route, from the given moment onward."""
        moment = when.astimezone(PERTH_TZ) if when else datetime.now(tz=PERTH_TZ)
        data = {
            "ExactlyMatchedRouteOnly": "true",
            "Mode": "bus",
            "Route": route,
            "QryDate": moment.strftime("%Y-%m-%d"),
            "QryTime": moment.strftime("%H:%M"),
            "MaxOptions": str(max_options),
        }
        body = await self._bus_post(AuthContext.ROUTE, route, OPTIONS_URL, data)
        payload = body.get("data") or {}
        direction = str(payload.get("Direction") or "outbound")
        trips = []
        for opt in payload.get("Options") or []:
            trips.append(
                RouteTrip(
                    route=route,
                    trip_key=opt.get("TripKey", ""),
                    route_uid=opt.get("RouteUid", ""),
                    direction=direction,
                    date=moment,
                    start_time=parse_clock_near(opt.get("StartTime") or "", moment),
                    finish_time=parse_clock_near(opt.get("FinishTime") or "", moment),
                    start_location=opt.get("StartLocation", ""),
                    finish_location=opt.get("FinishLocation", ""),
                )
            )
        return tuple(trips)

    async def get_trip_stops(self, trip: RouteTrip) -> tuple[TripStop, ...]:
        """Every stop on a trip; retries the opposite direction on null data."""
        opposite = "inbound" if trip.direction == "outbound" else "outbound"
        # start_time is already rolled past midnight when needed; trip.date
        # is only the query moment and can lag a day behind.
        trip_date = trip.start_time or trip.date
        payload: dict[str, Any] | None = None
        for direction in (trip.direction, opposite):
            data = {
                "RouteUid": trip.route_uid,
                "TripUid": trip.trip_key,
                "TripDate": trip_date.strftime("%Y-%m-%d"),
                "TripDirection": direction,
                "ReturnNoteCodes": NOTE_CODES,
            }
            body = await self._bus_post(AuthContext.ROUTE, trip.route, TRIP_URL, data)
            payload = body.get("data")
            if payload:
                break
        if not payload:
            return ()
        stops = []
        for timing in payload.get("TripStopTimings") or []:
            stop = timing.get("Stop") or {}
            stops.append(
                TripStop(
                    code=stop.get("Code", ""),
                    name=stop.get("Description", ""),
                    time=timing.get("DepartTime") or timing.get("ArrivalTime") or "",
                    can_board=bool(timing.get("CanBoard")),
                    can_alight=bool(timing.get("CanAlight")),
                    is_timing_point=bool(timing.get("IsTimingPoint")),
                    zone=stop.get("Zone"),
                    latitude=stop.get("Latitude"),
                    longitude=stop.get("Longitude"),
                )
            )
        return tuple(stops)

    async def get_train_departures(
        self, line: str, station: str
    ) -> tuple[TrainDeparture, ...]:
        """Live departures for a station on a line.

        Line and station are display names, e.g. "Midland Line", "Maylands Stn".
        Raises InvalidStopError when Transperth doesn't recognise the station.
        """
        url = TRAIN_STATUS_URL_TEMPLATE.format(
            line=quote(line, safe=""), station=quote(station, safe="")
        )
        text = await self._get(url, TRAIN_HEADERS)
        try:
            body: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError as err:
            raise TransperthError(f"Non-JSON response from {url}") from err
        data = body.get("data") or {}
        station_field = str(data.get("Station", ""))
        if "check spelling" in station_field.lower():
            raise InvalidStopError(
                f"Transperth does not know station {station!r} on {line!r}"
            )
        departures = []
        for entry in data.get("StatusDetailList") or []:
            try:
                departures.append(TrainDeparture.from_api(entry))
            except (KeyError, ValueError):
                continue
        return tuple(departures)

    async def get_train_lines(self) -> tuple[str, ...]:
        """All train line names, parsed from the Live Train Times page."""
        html = await self._get(LIVE_TRAIN_TIMES_PAGE, {"User-Agent": USER_AGENT})
        return parse_lines(html)

    async def get_train_stations(self) -> tuple[TrainStation, ...]:
        """All train stations, parsed from the Live Train Times page."""
        html = await self._get(LIVE_TRAIN_TIMES_PAGE, {"User-Agent": USER_AGENT})
        return parse_stations(html)

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
