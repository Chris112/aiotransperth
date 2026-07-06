"""Typed models and time parsing for Transperth API payloads.

All API times are naive local strings; every datetime this library
produces is timezone-aware Australia/Perth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
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
