import json
from datetime import datetime
from pathlib import Path

import pytest
from aioresponses import aioresponses
from yarl import URL

from aiotransperth.client import TransperthClient
from aiotransperth.const import STOP_TIMETABLE_URL
from aiotransperth.exceptions import InvalidStopError
from aiotransperth.models import PERTH_TZ

STOP_PAGE = (
    "https://www.transperth.wa.gov.au/Journey-Planner/Stops-Near-You"
    "?locationtype=stop&location=12627"
)
TOKEN_HTML = (
    '<input name="__RequestVerificationToken" type="hidden" value="tok123" />'
)
FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "stop_timetable.json").read_text()
)


async def test_get_stop_timetable() -> None:
    with aioresponses() as mock:
        mock.get(STOP_PAGE, body=TOKEN_HTML)
        mock.post(STOP_TIMETABLE_URL, payload=FIXTURE)
        async with TransperthClient() as client:
            tt = await client.get_stop_timetable(
                "12627", when=datetime(2026, 7, 6, 13, 40, tzinfo=PERTH_TZ)
            )
    assert tt.stop.code == "12627"
    assert len(tt.departures) == 2
    assert tt.departures[0].delay_minutes == 3


async def test_get_stop_timetable_sends_realtime_and_when() -> None:
    with aioresponses() as mock:
        mock.get(STOP_PAGE, body=TOKEN_HTML)
        mock.post(STOP_TIMETABLE_URL, payload=FIXTURE)
        async with TransperthClient() as client:
            await client.get_stop_timetable(
                "12627",
                when=datetime(2026, 7, 6, 13, 40, tzinfo=PERTH_TZ),
                max_trips=10,
            )
        sent = mock.requests[("POST", URL(STOP_TIMETABLE_URL))][0].kwargs["data"]
    assert sent["IsRealTimeChecked"] == "true"
    assert sent["SearchDate"] == "2026-07-06"
    assert sent["SearchTime"] == "13:40"
    assert sent["MaxTripCount"] == "10"
    assert sent["StopNumber"] == "12627"


async def test_missing_stop_metadata_raises_invalid_stop() -> None:
    bogus_page = (
        "https://www.transperth.wa.gov.au/Journey-Planner/Stops-Near-You"
        "?locationtype=stop&location=00000"
    )
    with aioresponses() as mock:
        mock.get(bogus_page, body=TOKEN_HTML)
        mock.post(
            STOP_TIMETABLE_URL,
            payload={"result": "success", "trips": [], "stop": None},
        )
        async with TransperthClient() as client:
            with pytest.raises(InvalidStopError):
                await client.validate_stop("00000")
