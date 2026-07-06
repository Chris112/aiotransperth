import json
from pathlib import Path
from urllib.parse import quote

import pytest
from aioresponses import aioresponses

from aiotransperth.client import TransperthClient
from aiotransperth.const import LIVE_TRAIN_TIMES_PAGE, TRAIN_STATUS_URL_TEMPLATE
from aiotransperth.exceptions import InvalidStopError

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "train_status.json").read_text()
)
PAGE_HTML = (
    Path(__file__).parent / "fixtures" / "live_train_times_page.html"
).read_text()


def _status_url(line: str, station: str) -> str:
    return TRAIN_STATUS_URL_TEMPLATE.format(
        line=quote(line, safe=""), station=quote(station, safe="")
    )


async def test_get_train_departures() -> None:
    with aioresponses() as mock:
        mock.get(_status_url("Midland Line", "Maylands Stn"), payload=FIXTURE)
        async with TransperthClient() as client:
            deps = await client.get_train_departures("Midland Line", "Maylands Stn")
    assert len(deps) == 2
    assert deps[0].destination == "Perth"
    assert deps[1].delay_minutes == 4


async def test_unknown_station_raises_invalid_stop() -> None:
    bad = {
        "result": "success",
        "data": {
            "Station": (
                "Perth. No Times available. Please check spelling of Station Name"
            ),
            "LastUpdated": "06/07/2026 at 13:56:30",
            "StatusDetailList": [],
        },
    }
    with aioresponses() as mock:
        mock.get(_status_url("Midland Line", "Perth"), payload=bad)
        async with TransperthClient() as client:
            with pytest.raises(InvalidStopError):
                await client.get_train_departures("Midland Line", "Perth")


async def test_get_train_lines_and_stations() -> None:
    with aioresponses() as mock:
        mock.get(LIVE_TRAIN_TIMES_PAGE, body=PAGE_HTML)
        mock.get(LIVE_TRAIN_TIMES_PAGE, body=PAGE_HTML)
        async with TransperthClient() as client:
            lines = await client.get_train_lines()
            stations = await client.get_train_stations()
    assert "Midland Line" in lines and len(lines) == 8
    assert any(s.name == "Maylands Stn" for s in stations)
