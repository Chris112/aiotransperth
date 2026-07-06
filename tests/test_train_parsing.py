import json
from datetime import datetime
from pathlib import Path

from aiotransperth.models import PERTH_TZ, Mode, TrainDeparture

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "train_status.json").read_text()
)
ENTRIES = FIXTURE["data"]["StatusDetailList"]


def test_on_time_train() -> None:
    dep = TrainDeparture.from_api(ENTRIES[0])
    assert dep.line == "Midland Line"
    assert dep.destination == "Perth"
    assert dep.platform == "1"
    assert dep.cars == 4
    assert dep.scheduled == datetime(2026, 7, 6, 14, 6, tzinfo=PERTH_TZ)
    assert dep.estimated == dep.scheduled
    assert dep.delay_minutes == 0
    assert dep.live.is_live and dep.live.description == "On Time"
    assert dep.mode is Mode.TRAIN


def test_delayed_train() -> None:
    dep = TrainDeparture.from_api(ENTRIES[1])
    assert dep.scheduled == datetime(2026, 7, 6, 14, 4, tzinfo=PERTH_TZ)
    assert dep.estimated == datetime(2026, 7, 6, 14, 8, tzinfo=PERTH_TZ)
    assert dep.delay_minutes == 4
    assert dep.live.status_code == 2
    assert dep.trip_id == 6880212
