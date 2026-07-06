from pathlib import Path

from aiotransperth.models import TrainStation
from aiotransperth.stations import parse_lines, parse_stations

HTML = (
    Path(__file__).parent / "fixtures" / "live_train_times_page.html"
).read_text()


def test_parse_lines_excludes_all_placeholder() -> None:
    lines = parse_lines(HTML)
    assert lines == (
        "Airport Line",
        "Armadale Line",
        "Ellenbrook Line",
        "Fremantle Line",
        "Mandurah Line",
        "Midland Line",
        "Thornlie-Cockburn Line",
        "Yanchep Line",
    )


def test_parse_stations() -> None:
    stations = parse_stations(HTML)
    assert TrainStation(id="130", name="Maylands Stn") in stations
    assert len(stations) == 4
    assert all(s.name.endswith("Stn") for s in stations)
