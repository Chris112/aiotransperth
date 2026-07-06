from datetime import datetime

import pytest

from aiotransperth.models import (
    NOT_LIVE,
    PERTH_TZ,
    LiveStatus,
    Mode,
    Stop,
    TrainStation,
    parse_clock_near,
    parse_iso_perth,
)


def test_parse_iso_perth_is_aware() -> None:
    dt = parse_iso_perth("2026-07-06T13:45")
    assert dt == datetime(2026, 7, 6, 13, 45, tzinfo=PERTH_TZ)
    assert dt.tzinfo is PERTH_TZ


def test_parse_iso_perth_ignores_seconds_suffix() -> None:
    assert parse_iso_perth("2026-07-06T13:45:00").minute == 45


def test_parse_clock_near_12h() -> None:
    anchor = datetime(2026, 7, 6, 13, 45, tzinfo=PERTH_TZ)
    assert parse_clock_near("1:48pm", anchor) == anchor.replace(hour=13, minute=48)


def test_parse_clock_near_24h() -> None:
    anchor = datetime(2026, 7, 6, 14, 4, tzinfo=PERTH_TZ)
    assert parse_clock_near("14:07", anchor) == anchor.replace(minute=7)


def test_parse_clock_near_rolls_past_midnight() -> None:
    anchor = datetime(2026, 7, 6, 23, 58, tzinfo=PERTH_TZ)
    result = parse_clock_near("12:05am", anchor)
    assert result is not None and result.day == 7


def test_parse_clock_near_garbage_returns_none() -> None:
    anchor = datetime(2026, 7, 6, 13, 0, tzinfo=PERTH_TZ)
    assert parse_clock_near("cancelled", anchor) is None


def test_models_frozen() -> None:
    stop = Stop(code="12627", name="Main St After Lawley St", zone="1", mode=Mode.BUS)
    with pytest.raises(AttributeError):
        stop.code = "x"  # type: ignore[misc]
    assert LiveStatus(is_live=False, status_code=None, description="") == NOT_LIVE
    assert TrainStation(id="130", name="Maylands Stn").name == "Maylands Stn"
