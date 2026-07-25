"""Async client for Transperth (Perth, WA) bus and train departures."""

from .client import TransperthClient
from .exceptions import (
    AuthError,
    InvalidStopError,
    NetworkError,
    RateLimitError,
    TransperthError,
)
from .lines import (
    is_known_journey,
    known_lines,
    line_endpoints,
    line_stations,
    serves_journey,
)
from .models import (
    PERTH_TZ,
    BusDeparture,
    LiveStatus,
    Mode,
    RouteTrip,
    Stop,
    StopTimetable,
    TrainDeparture,
    TrainStation,
    TripStop,
)

__version__ = "0.2.0"

__all__ = [
    "PERTH_TZ",
    "AuthError",
    "BusDeparture",
    "InvalidStopError",
    "LiveStatus",
    "Mode",
    "NetworkError",
    "RateLimitError",
    "RouteTrip",
    "Stop",
    "StopTimetable",
    "TrainDeparture",
    "TrainStation",
    "TransperthClient",
    "TransperthError",
    "TripStop",
    "is_known_journey",
    "known_lines",
    "line_endpoints",
    "line_stations",
    "serves_journey",
]
