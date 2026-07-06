import json
from datetime import datetime
from pathlib import Path

from aiotransperth.models import PERTH_TZ, BusDeparture, StopTimetable

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "stop_timetable.json").read_text()
)


def test_live_departure_parses_delay() -> None:
    dep = BusDeparture.from_api(FIXTURE["trips"][0])
    assert dep.route == "402"
    assert dep.scheduled == datetime(2026, 7, 6, 13, 45, tzinfo=PERTH_TZ)
    assert dep.estimated == datetime(2026, 7, 6, 13, 48, tzinfo=PERTH_TZ)
    assert dep.delay_minutes == 3
    assert dep.live.is_live and dep.live.status_code == 2
    assert dep.live.description == "3 min delay"
    assert dep.destination == "Perth Busport Zone B"


def test_scheduled_departure_has_no_estimate() -> None:
    dep = BusDeparture.from_api(FIXTURE["trips"][1])
    assert dep.route == "414"
    assert dep.estimated is None
    assert dep.delay_minutes is None
    assert not dep.live.is_live and dep.live.description == ""


def test_timetable_skips_malformed_entries() -> None:
    tt = StopTimetable.from_api(FIXTURE)
    assert tt.stop.code == "12627"
    assert tt.stop.name == "Main St After Lawley St"
    assert tt.stop.zone == "1"
    assert len(tt.departures) == 2  # third trip has no time -> skipped
