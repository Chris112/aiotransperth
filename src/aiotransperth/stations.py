"""Parse the train line/station catalog from the Live Train Times page.

The page server-renders both dropdowns; no JSON endpoint exists for them.
"""

from __future__ import annotations

import re

from .models import TrainStation

_LINE_RE = re.compile(r'<option value="([^"]+ Line)">')
_STATION_RE = re.compile(r'<option value="(\d+)">([^<]+ Stn)</option>')


def parse_lines(html: str) -> tuple[str, ...]:
    """All train line names, e.g. 'Midland Line' (excludes the 'All' option)."""
    return tuple(_LINE_RE.findall(html))


def parse_stations(html: str) -> tuple[TrainStation, ...]:
    """All train stations with their numeric page IDs."""
    return tuple(
        TrainStation(id=sid, name=name) for sid, name in _STATION_RE.findall(html)
    )
