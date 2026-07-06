import json
from datetime import datetime
from pathlib import Path

from aioresponses import aioresponses
from yarl import URL

from aiotransperth.client import TransperthClient
from aiotransperth.const import OPTIONS_URL, TRIP_URL
from aiotransperth.models import PERTH_TZ, RouteTrip

ROUTE_PAGE = "https://www.transperth.wa.gov.au/timetables/details?Bus=414"
TOKEN_HTML = (
    '<input name="__RequestVerificationToken" type="hidden" value="tok123" />'
)
OPTIONS = json.loads((Path(__file__).parent / "fixtures" / "options.json").read_text())
TRIP = json.loads((Path(__file__).parent / "fixtures" / "trip.json").read_text())
WHEN = datetime(2026, 7, 6, 22, 30, tzinfo=PERTH_TZ)


async def test_get_route_trips() -> None:
    with aioresponses() as mock:
        mock.get(ROUTE_PAGE, body=TOKEN_HTML)
        mock.post(OPTIONS_URL, payload=OPTIONS)
        async with TransperthClient() as client:
            trips = await client.get_route_trips("414", when=WHEN)
    trip = trips[0]
    assert trip.trip_key == "PerthRestricted:6423575"
    assert trip.direction == "outbound"
    assert trip.start_time == datetime(2026, 7, 6, 23, 8, tzinfo=PERTH_TZ)
    assert trip.start_location == "Stirling Stn Stand B"


async def test_get_trip_stops() -> None:
    trip = RouteTrip(
        route="414",
        trip_key="PerthRestricted:6423575",
        route_uid="PerthRestricted:SWA-MAR-2504",
        direction="outbound",
        date=WHEN,
        start_time=None,
        finish_time=None,
        start_location="",
        finish_location="",
    )
    with aioresponses() as mock:
        mock.get(ROUTE_PAGE, body=TOKEN_HTML)
        mock.post(TRIP_URL, payload=TRIP)
        async with TransperthClient() as client:
            stops = await client.get_trip_stops(trip)
    assert len(stops) == 2
    assert stops[0].code == "29720" and stops[0].can_board and not stops[0].can_alight
    assert stops[1].time == "23:19"


async def test_get_trip_stops_uses_start_time_date_after_midnight() -> None:
    # Queried at 22:30 on the 6th; the trip starts 00:15 on the 7th.
    trip = RouteTrip(
        route="414",
        trip_key="PerthRestricted:6423575",
        route_uid="PerthRestricted:SWA-MAR-2504",
        direction="outbound",
        date=WHEN,
        start_time=datetime(2026, 7, 7, 0, 15, tzinfo=PERTH_TZ),
        finish_time=None,
        start_location="",
        finish_location="",
    )
    with aioresponses() as mock:
        mock.get(ROUTE_PAGE, body=TOKEN_HTML)
        mock.post(TRIP_URL, payload=TRIP)
        async with TransperthClient() as client:
            await client.get_trip_stops(trip)
    calls = mock.requests[("POST", URL(TRIP_URL))]
    assert calls[0].kwargs["data"]["TripDate"] == "2026-07-07"


async def test_get_trip_stops_direction_fallback() -> None:
    trip = RouteTrip(
        route="414",
        trip_key="PerthRestricted:6423575",
        route_uid="PerthRestricted:SWA-MAR-2504",
        direction="inbound",  # wrong on purpose: first call returns null data
        date=WHEN,
        start_time=None,
        finish_time=None,
        start_location="",
        finish_location="",
    )
    with aioresponses() as mock:
        mock.get(ROUTE_PAGE, body=TOKEN_HTML)
        mock.post(TRIP_URL, payload={"result": "success", "data": None})
        mock.post(TRIP_URL, payload=TRIP)
        async with TransperthClient() as client:
            stops = await client.get_trip_stops(trip)
    assert len(stops) == 2
