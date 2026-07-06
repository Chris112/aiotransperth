"""Typed models and time parsing for Transperth API payloads.

All API times are naive local strings; every datetime this library
produces is timezone-aware Australia/Perth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

PERTH_TZ = ZoneInfo("Australia/Perth")


class Mode(StrEnum):
    BUS = "bus"
    TRAIN = "train"


def parse_iso_perth(value: str) -> datetime:
    """Parse '2026-07-06T13:45' (Perth local, no offset) to an aware datetime."""
    return datetime.strptime(value[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=PERTH_TZ)


def parse_clock_near(clock: str, anchor: datetime) -> datetime | None:
    """Parse a bare clock string ('1:48pm' or '14:04') onto anchor's date.

    Rolls forward one day when the result lands more than 12 h before the
    anchor (a departure display just past midnight). Returns None for
    unparseable strings (e.g. status text instead of a time).
    """
    text = clock.strip().lower().replace(" ", "")
    parsed: datetime | None = None
    for fmt in ("%I:%M%p", "%H:%M"):
        try:
            parsed = datetime.strptime(text, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        return None
    result = anchor.replace(
        hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0
    )
    if result < anchor - timedelta(hours=12):
        result += timedelta(days=1)
    return result


@dataclass(frozen=True, slots=True)
class LiveStatus:
    """Realtime tracking state for one departure."""

    is_live: bool
    status_code: int | None  # raw API code; known: bus 2=delayed, train 1=on time
    description: str  # e.g. "On Time", "3 min delay"; "" when not live


NOT_LIVE = LiveStatus(is_live=False, status_code=None, description="")


@dataclass(frozen=True, slots=True)
class Stop:
    """A bus stop (or, later, any boarding point)."""

    code: str
    name: str
    zone: str | None = None
    mode: Mode = Mode.BUS


@dataclass(frozen=True, slots=True)
class TrainStation:
    """A train station from the live-times catalog."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class BusDeparture:
    """One upcoming bus at a stop."""

    route: str
    headsign: str
    destination: str
    origin: str
    scheduled: datetime
    estimated: datetime | None
    live: LiveStatus
    trip_uid: str
    mode: Mode = Mode.BUS

    @property
    def delay_minutes(self) -> int | None:
        """Minutes behind schedule (negative = early); None when not live."""
        if self.estimated is None:
            return None
        return round((self.estimated - self.scheduled).total_seconds() / 60)

    @classmethod
    def from_api(cls, entry: dict[str, Any]) -> BusDeparture:
        """Parse one GetStopTimetableAsync trips[] entry.

        Raises ValueError when the entry has no usable departure time.
        """
        summary = entry.get("Summary") or {}
        time_str = entry.get("DepartTime") or entry.get("ArriveTime") or ""
        scheduled = parse_iso_perth(time_str)
        is_live = bool(entry.get("IsRealTime"))
        estimated = (
            parse_clock_near(entry.get("DisplayTripStatus") or "", scheduled)
            if is_live
            else None
        )
        live = (
            LiveStatus(
                is_live=True,
                status_code=entry.get("RealTimeStopStatus"),
                description=entry.get("RealTimeStopStatusDetail") or "",
            )
            if is_live
            else NOT_LIVE
        )
        return cls(
            route=summary.get("RouteCode", ""),
            headsign=summary.get("Headsign", ""),
            destination=(entry.get("Destination") or {}).get("Name", ""),
            origin=(entry.get("Origin") or {}).get("Name", ""),
            scheduled=scheduled,
            estimated=estimated,
            live=live,
            trip_uid=summary.get("TripUid", ""),
        )


@dataclass(frozen=True, slots=True)
class TrainDeparture:
    """One upcoming train at a station."""

    line: str
    destination: str
    platform: str
    scheduled: datetime
    estimated: datetime | None
    live: LiveStatus
    cars: int | None
    pattern: str
    trip_id: int
    mode: Mode = Mode.TRAIN

    @property
    def delay_minutes(self) -> int | None:
        """Minutes behind schedule (negative = early); None when not live."""
        if self.estimated is None:
            return None
        return round((self.estimated - self.scheduled).total_seconds() / 60)

    @classmethod
    def from_api(cls, entry: dict[str, Any]) -> TrainDeparture:
        """Parse one GetStationLiveStatusAsync StatusDetailList[] entry."""
        scheduled = datetime.strptime(
            entry["TripStopSchedule"], "%d/%m/%Y %H:%M:%S"
        ).replace(tzinfo=PERTH_TZ)
        is_live = bool(entry.get("IsRealTime"))
        estimated = (
            parse_clock_near(entry.get("Departure") or "", scheduled)
            if is_live
            else None
        )
        try:
            cars: int | None = int(entry.get("Ncar") or "")
        except ValueError:
            cars = None
        return cls(
            line=entry.get("LineName", ""),
            destination=entry.get("Destination", ""),
            platform=entry.get("Platform", ""),
            scheduled=scheduled,
            estimated=estimated,
            live=LiveStatus(
                is_live=is_live,
                status_code=entry.get("Status"),
                description=entry.get("StatusDetail") or "",
            ),
            cars=cars,
            pattern=entry.get("Pattern", ""),
            trip_id=int(entry.get("TripId") or 0),
        )


@dataclass(frozen=True, slots=True)
class StopTimetable:
    """A stop plus its upcoming departures."""

    stop: Stop
    departures: tuple[BusDeparture, ...]

    @classmethod
    def from_api(cls, body: dict[str, Any]) -> StopTimetable:
        """Parse a full GetStopTimetableAsync response; skips malformed trips."""
        stop_raw = body.get("stop") or {}
        stop = Stop(
            code=stop_raw.get("Code", ""),
            name=stop_raw.get("Description", ""),
            zone=stop_raw.get("Zone"),
        )
        departures = []
        for entry in body.get("trips") or []:
            try:
                departures.append(BusDeparture.from_api(entry))
            except ValueError:
                continue
        return cls(stop=stop, departures=tuple(departures))
