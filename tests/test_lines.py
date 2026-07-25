import pytest

from aiotransperth import lines
from aiotransperth.lines import (
    is_known_journey,
    line_endpoints,
    line_stations,
    serves_journey,
)

# "Test Line" is city-radial. "Cross Line" runs through the CBD and out the
# other side, like the real Airport Line reaching Claremont — the city sits
# mid-route, so nothing may assume it is at index 0.
SYNTHETIC = {
    "Test Line": (
        "Perth Stn",
        "Alpha Stn",
        "Beta Stn",
        "Gamma Stn",
        "Delta Stn",
    ),
    # Serves Perth Underground, but its departures still say "Perth".
    "North Line": (
        "Perth Underground Stn",
        "Near Stn",
        "Far Stn",
    ),
    "Wide Line": (
        "East Two Stn",
        "East One Stn",
        "Perth Stn",
        "West One Stn",
        "West Two Stn",
    ),
}


@pytest.fixture(autouse=True)
def _synthetic_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lines, "LINE_STATIONS", SYNTHETIC)


def test_line_stations_is_route_ordered() -> None:
    assert line_stations("Test Line")[0] == "Perth Stn"
    assert line_stations("Test Line")[-1] == "Delta Stn"


def test_line_endpoints() -> None:
    assert line_endpoints("Test Line") == ("Perth Stn", "Delta Stn")


def test_is_known_journey() -> None:
    assert is_known_journey("Test Line", "Beta Stn", "Perth Stn")
    assert not is_known_journey("Test Line", "Beta Stn", "Nowhere Stn")
    assert not is_known_journey("Other Line", "Beta Stn", "Perth Stn")


def test_serves_cityward_and_outbound() -> None:
    assert serves_journey("Test Line", "Beta Stn", "Perth Stn", "Perth Stn")
    assert serves_journey("Test Line", "Beta Stn", "Delta Stn", "Delta Stn")


def test_wrong_direction_is_excluded() -> None:
    # A Delta-bound train is no use to someone heading for the city.
    assert not serves_journey("Test Line", "Beta Stn", "Delta Stn", "Perth Stn")
    assert not serves_journey("Test Line", "Beta Stn", "Perth Stn", "Delta Stn")


def test_short_working_kept_for_stations_it_reaches() -> None:
    # Terminates at Gamma: fine for Gamma, useless for Delta.
    assert serves_journey("Test Line", "Beta Stn", "Gamma Stn", "Gamma Stn")
    assert not serves_journey("Test Line", "Beta Stn", "Gamma Stn", "Delta Stn")


def test_short_working_cityward() -> None:
    # Terminates at Alpha, one short of the city.
    assert serves_journey("Test Line", "Beta Stn", "Alpha Stn", "Alpha Stn")
    assert not serves_journey("Test Line", "Beta Stn", "Alpha Stn", "Perth Stn")


def test_through_routed_terminus_counts_as_cityward() -> None:
    # A terminus on another line means the service runs through the CBD, so it
    # serves everything cityward — and nothing outbound.
    assert serves_journey("Test Line", "Beta Stn", "Mandurah Stn", "Perth Stn")
    assert serves_journey("Test Line", "Beta Stn", "Mandurah Stn", "Alpha Stn")
    assert not serves_journey("Test Line", "Beta Stn", "Mandurah Stn", "Delta Stn")


def test_same_station_serves_nothing() -> None:
    assert not serves_journey("Test Line", "Beta Stn", "Delta Stn", "Beta Stn")


def test_terminus_matches_without_the_stn_suffix() -> None:
    # Departures say "Gamma"; the catalog says "Gamma Stn".
    assert serves_journey("Test Line", "Beta Stn", "Gamma", "Gamma Stn")
    assert not serves_journey("Test Line", "Beta Stn", "Gamma", "Delta Stn")


def test_bare_city_name_resolves_to_this_lines_cbd_station() -> None:
    # Northern-line services say "Perth" though the line serves Perth
    # Underground. That must mean "terminates at the city", not "runs past it".
    assert serves_journey("North Line", "Far Stn", "Perth", "Perth Underground Stn")
    assert serves_journey("North Line", "Far Stn", "Perth", "Near Stn")
    assert not serves_journey("North Line", "Near Stn", "Perth", "Far Stn")


def test_city_terminating_service_does_not_cross_to_the_far_side() -> None:
    # On a line spanning the CBD, a Perth-terminating service is no use for
    # continuing out the other side — unlike one that genuinely runs through.
    assert not serves_journey("Wide Line", "East One Stn", "Perth", "West One Stn")
    assert serves_journey("Wide Line", "East One Stn", "West Two Stn", "West One Stn")


def test_offline_terminus_on_a_cbd_spanning_line_runs_through_the_centre() -> None:
    assert serves_journey("Wide Line", "East Two Stn", "Mandurah", "Perth Stn")
    assert serves_journey("Wide Line", "East Two Stn", "Mandurah", "East One Stn")
    assert not serves_journey("Wide Line", "East Two Stn", "Mandurah", "West One Stn")


def test_at_the_cbd_an_offline_terminus_is_ambiguous() -> None:
    assert not serves_journey("Wide Line", "Perth Stn", "Mandurah", "West One Stn")
    assert not serves_journey("Wide Line", "Perth Stn", "Mandurah", "East One Stn")


def test_unknown_line_and_station_are_caller_errors() -> None:
    with pytest.raises(KeyError):
        serves_journey("Nope Line", "Beta Stn", "Perth Stn", "Perth Stn")
    with pytest.raises(ValueError):
        serves_journey("Test Line", "Nowhere Stn", "Perth Stn", "Perth Stn")
