"""Invariants for the generated table in `_line_data.py`.

`test_lines.py` swaps in a synthetic network to test the direction logic; this
file checks the real generated data instead, so a bad regeneration fails here
rather than silently producing wrong journeys.
"""

from aiotransperth._line_data import LINE_STATIONS
from aiotransperth.const import CBD_STATIONS


def test_table_is_populated() -> None:
    assert LINE_STATIONS, "run scripts/generate_line_order.py"
    assert len(LINE_STATIONS) >= 7, LINE_STATIONS.keys()


def test_every_line_is_a_usable_route() -> None:
    for line, order in LINE_STATIONS.items():
        assert len(order) >= 2, line
        assert len(set(order)) == len(order), f"{line} repeats a station: {order}"
        assert all(s.endswith(" Stn") for s in order), line


def test_every_line_reaches_the_city() -> None:
    # serves_journey resolves any off-line terminus to the line's CBD station,
    # so a line without one can't answer direction questions at all.
    for line, order in LINE_STATIONS.items():
        assert set(order) & CBD_STATIONS, f"{line} has no CBD station: {order}"


def test_index_zero_is_the_end_nearer_the_city() -> None:
    for line, order in LINE_STATIONS.items():
        cbd = next(i for i, s in enumerate(order) if s in CBD_STATIONS)
        assert cbd <= len(order) - 1 - cbd, f"{line} is oriented away from the city"


def test_yanchep_line_matches_the_real_network() -> None:
    order = LINE_STATIONS["Yanchep Line"]
    assert order[-1] == "Yanchep Stn"
    assert "Perth Underground Stn" in order
    # Edgewater sits between Joondalup and the city, not beyond Joondalup.
    assert order.index("Edgewater Stn") < order.index("Joondalup Stn")
    assert order.index("Joondalup Stn") < order.index("Butler Stn")
