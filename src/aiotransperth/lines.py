"""Direction and reachability along a train line.

Transperth's live payload says only where a service *terminates*, never which
way it is heading. Everything here derives direction from the route-ordered
station table in `_line_data.py`, which is generated from live trip data by
`scripts/generate_line_order.py`.

Lines are not all city-radial: the Airport Line runs through the CBD and out
to Claremont on the Fremantle Line, so its centre — not its end — is the city.
Direction and reachability are therefore computed from relative positions and
never assume where the CBD sits. Index 0 is merely the end nearer the CBD.

Names need normalising before they can be compared. The catalog calls a
station "Perth Stn"; a departure bound for it says "Perth". City-bound
services on the northern lines say "Perth" even though those lines serve
Perth Underground rather than Perth Stn, so any terminus the line doesn't
name resolves to whichever CBD station it does have.
"""

from __future__ import annotations

from ._line_data import LINE_STATIONS
from .const import CBD_STATIONS

__all__ = [
    "CBD_STATIONS",
    "LINE_STATIONS",
    "is_known_journey",
    "known_lines",
    "line_endpoints",
    "line_stations",
    "serves_journey",
]


def _key(name: str) -> str:
    """Comparable form of a station or destination name."""
    return name.strip().removesuffix(" Stn").removesuffix(" Station").casefold()


_CBD_KEYS = frozenset(_key(name) for name in CBD_STATIONS)


def _positions(order: tuple[str, ...]) -> dict[str, int]:
    return {_key(station): i for i, station in enumerate(order)}


def _cbd_index(order: tuple[str, ...]) -> int | None:
    """Position of this line's city interchange, or None if it has none."""
    for i, station in enumerate(order):
        if _key(station) in _CBD_KEYS:
            return i
    return None


def known_lines() -> tuple[str, ...]:
    """Lines the ordering table covers, alphabetically.

    Callers offering a line picker should use this rather than the live
    catalog, so a line can never be chosen that direction logic can't answer.
    """
    return tuple(sorted(LINE_STATIONS))


def line_stations(line: str) -> tuple[str, ...]:
    """Stations on `line` in route order, city end first.

    Raises KeyError for a line absent from the table.
    """
    return LINE_STATIONS[line]


def line_endpoints(line: str) -> tuple[str, str]:
    """The `(inner, outer)` end stations of `line`."""
    order = LINE_STATIONS[line]
    return order[0], order[-1]


def is_known_journey(line: str, station: str, target: str) -> bool:
    """Whether both stations are on `line` in the generated table.

    Callers that persist station names (config entries, caches) should check
    this before relying on `serves_journey`, since the table is a snapshot and
    the network occasionally gains stations.
    """
    order = LINE_STATIONS.get(line)
    if order is None:
        return False
    positions = _positions(order)
    return _key(station) in positions and _key(target) in positions


def serves_journey(line: str, station: str, terminus: str, target: str) -> bool:
    """Whether a service terminating at `terminus` carries you `station`→`target`.

    True when the service runs the right way *and* goes at least as far as
    `target`, so a short-working is kept for the stations it actually reaches
    and dropped for those it doesn't.

    A `terminus` naming no station on this line — a bare "Perth", or somewhere
    on another line entirely — means the service ends its run with this line
    at the CBD: either it terminates in the city, or it diverges there onto
    another line. Both cases are treated as terminating at this line's CBD
    station, so such a service carries you toward the centre but never out the
    far side of a line that spans it.

    Raises KeyError for an unknown line, ValueError when `station` or `target`
    is not on it — both are caller errors; use `is_known_journey` to check.
    """
    order = LINE_STATIONS[line]
    positions = _positions(order)
    try:
        here = positions[_key(station)]
        there = positions[_key(target)]
    except KeyError as err:
        raise ValueError(f"{station!r}/{target!r} not both on {line!r}") from err

    terminus_key = _key(terminus)
    if terminus_key in positions:
        end = positions[terminus_key]
    else:
        cbd = _cbd_index(order)
        if cbd is None:
            return False
        end = cbd

    heading = there - here
    reaches = end - here
    if heading == 0:
        return False
    if (heading > 0) != (reaches > 0):
        return False
    return abs(reaches) >= abs(heading)
