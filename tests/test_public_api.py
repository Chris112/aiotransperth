import aiotransperth


def test_public_surface() -> None:
    for name in (
        "TransperthClient",
        "BusDeparture",
        "TrainDeparture",
        "StopTimetable",
        "Stop",
        "TrainStation",
        "RouteTrip",
        "TripStop",
        "LiveStatus",
        "Mode",
        "PERTH_TZ",
        "TransperthError",
        "RateLimitError",
        "AuthError",
        "NetworkError",
        "InvalidStopError",
    ):
        assert hasattr(aiotransperth, name), name
    assert aiotransperth.__version__ == "0.1.0"
