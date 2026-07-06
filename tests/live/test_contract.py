"""Contract tests against the real Transperth API.

Run deliberately: pytest -m live
Never run in loops — the 429 cooldown is sticky (>60 s) and shared with
the public website. Fixed inputs: bus 414 / stop 12627 / Maylands Stn,
tomorrow midday for buses (guarantees a non-empty schedule).
"""

from datetime import datetime, timedelta

import pytest

from aiotransperth import (
    PERTH_TZ,
    InvalidStopError,
    Mode,
    TransperthClient,
)

pytestmark = pytest.mark.live

TEST_STOP = "12627"
TEST_ROUTE = "414"


def _tomorrow_midday() -> datetime:
    return (datetime.now(tz=PERTH_TZ) + timedelta(days=1)).replace(
        hour=13, minute=0, second=0, microsecond=0
    )


async def test_live_stop_timetable() -> None:
    async with TransperthClient() as client:
        tt = await client.get_stop_timetable(TEST_STOP, when=_tomorrow_midday())
    assert tt.stop.code == TEST_STOP
    assert tt.departures, "no departures at midday tomorrow — schema drift?"
    dep = tt.departures[0]
    assert dep.route and dep.scheduled.tzinfo is PERTH_TZ
    assert dep.mode is Mode.BUS


async def test_live_invalid_stop() -> None:
    async with TransperthClient() as client:
        with pytest.raises(InvalidStopError):
            await client.validate_stop("00000999")


async def test_live_route_trips_and_stops() -> None:
    async with TransperthClient() as client:
        trips = await client.get_route_trips(TEST_ROUTE, when=_tomorrow_midday())
        assert trips and trips[0].trip_key
        stops = await client.get_trip_stops(trips[0])
    assert len(stops) > 1
    assert all(s.code for s in stops)


async def test_live_train_departures() -> None:
    async with TransperthClient() as client:
        deps = await client.get_train_departures("Midland Line", "Maylands Stn")
    # Empty overnight is legitimate; shape is what we pin.
    for dep in deps:
        assert dep.scheduled.tzinfo is PERTH_TZ
        assert dep.destination
        assert dep.line == "Midland Line"


async def test_live_train_catalog() -> None:
    async with TransperthClient() as client:
        lines = await client.get_train_lines()
        stations = await client.get_train_stations()
    assert "Midland Line" in lines and len(lines) == 8
    assert any(s.name == "Maylands Stn" for s in stations)
    assert len(stations) > 60
