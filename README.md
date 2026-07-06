# aiotransperth

Live Perth bus and train departures in Python — including realtime delays.

Transperth (Perth, Western Australia's public transport operator) publishes
no official realtime API. Live delay data exists in exactly one place: the
Transperth website itself. This library talks to the same internal endpoints
the website uses and hands you the results as plain, typed Python objects —
the only way to get Perth realtime data into your own code.

- **Buses** — upcoming departures at any stop, live delays for buses already
  on the road, and stop-by-stop trip details.
- **Trains** — live departures for any station: destination, platform, delay
  status, car count.

Async (`aiohttp` is the only dependency), fully typed, Python 3.12+, MIT.

## Getting started

Not on PyPI yet — install from a checkout:

```bash
git clone https://github.com/Chris112/aiotransperth
cd aiotransperth
pip install .
```

Then:

```python
import asyncio

from aiotransperth import TransperthClient


async def main() -> None:
    async with TransperthClient() as client:
        # ---- Buses: next departures at stop 12627 ----
        timetable = await client.get_stop_timetable("12627")
        print(f"Stop {timetable.stop.code}: {timetable.stop.name}")
        for dep in timetable.departures[:3]:
            when = dep.estimated or dep.scheduled  # live estimate if available
            live = f"live, {dep.live.description}" if dep.live.is_live else "scheduled"
            print(f"  {dep.route:>4} to {dep.headsign:<20} {when:%H:%M} ({live})")

        # ---- Trains: live status at Maylands on the Midland line ----
        trains = await client.get_train_departures("Midland Line", "Maylands Stn")
        print("Maylands Stn (Midland Line):")
        for train in trains[:3]:
            when = train.estimated or train.scheduled
            print(
                f"  to {train.destination:<8} plat {train.platform} "
                f"{when:%H:%M} ({train.live.description}, {train.cars} cars)"
            )


asyncio.run(main())
```

Real output (Monday afternoon, Perth):

```
Stop 12627: Main St After Royal St
   404 to Tuart Hill           15:20 (scheduled)
   402 to Perth Busport        15:22 (scheduled)
   414 to Glendalough Stn      15:33 (scheduled)
Maylands Stn (Midland Line):
  to Midland  plat 2 14:50 (On Time, 4 cars)
  to Perth    plat 1 14:57 (On Time, 4 cars)
  to Midland  plat 2 15:01 (On Time, 4 cars)
```

When a bus is live-tracked (typically the imminent departure), `dep.live.is_live`
is true, `dep.estimated` carries the actual expected time, and
`dep.delay_minutes` the difference — e.g. `3` for a bus running three minutes
late. Trains are always live-tracked while services run.

## Finding your inputs

- **Bus stop code** — the 5-digit number printed on the physical stop sign,
  also shown when you click a stop in the
  [Transperth journey planner](https://www.transperth.wa.gov.au). Verify one
  with `await client.validate_stop("12627")`, which returns the stop's name or
  raises `InvalidStopError`.
- **Train line and station names** — display names exactly as the Transperth
  site spells them: lines like `"Midland Line"`, stations like `"Maylands Stn"`.
  Don't guess; fetch the catalog:

  ```python
  lines = await client.get_train_lines()        # ("Airport Line", ..., "Yanchep Line")
  stations = await client.get_train_stations()  # (TrainStation(id="130", name="Maylands Stn"), ...)
  ```

## API

All methods are coroutines on `TransperthClient`. Construct it bare (it
manages its own `aiohttp` session as an async context manager) or pass your
own session, which will not be closed for you.

| Method | Returns | Notes |
|---|---|---|
| `get_stop_timetable(stop_code, *, when=None, max_trips=100)` | `StopTimetable` (stop + `BusDeparture` tuple) | Realtime always requested. `when` defaults to now (Perth). |
| `validate_stop(stop_code)` | `Stop` | Raises `InvalidStopError` for unknown codes. |
| `get_route_trips(route, *, when=None, max_options=4)` | `tuple[RouteTrip, ...]` | Upcoming trips for a route, e.g. `"414"`. |
| `get_trip_stops(trip)` | `tuple[TripStop, ...]` | Every stop on a trip, with times, boarding flags, GPS. |
| `get_train_departures(line, station)` | `tuple[TrainDeparture, ...]` | Live status; raises `InvalidStopError` for unknown stations. |
| `get_train_lines()` | `tuple[str, ...]` | The 8 line names. Fetched once, cached per client. |
| `get_train_stations()` | `tuple[TrainStation, ...]` | All ~80 stations. Fetched once, cached per client. |

Departure models share a core: `scheduled` and `estimated` (aware datetimes;
`estimated` is `None` when not live), `live` (a `LiveStatus` with `is_live`,
raw `status_code`, and a human `description`), and a `delay_minutes` property.
Buses add `route`, `headsign`, `origin`, `destination`, `trip_uid`; trains add
`line`, `destination`, `platform`, `cars`, `pattern`, `trip_id`.

## Errors

Everything raises a subclass of `TransperthError`:

| Exception | Meaning | What to do |
|---|---|---|
| `RateLimitError` | HTTP 429 — Transperth's cooldown is sticky (>60 s) and shared with their public website | Back off for minutes, not seconds |
| `AuthError` | A CSRF token couldn't be obtained or was rejected (bus endpoints only) | Usually transient; the client already retried once |
| `NetworkError` | DNS/timeout/connection failure | Retry with your own policy |
| `InvalidStopError` | Unknown stop code or station name | Fix the input |

The client itself never sleeps and never retries beyond one automatic token
refresh on HTTP 401 — back-off policy belongs to the caller.

## Data caveats

- This is an **unofficial** API; Transperth can change or break it without
  notice. A `-m live` contract test suite pins the shapes this library reads.
- Individual departures the API garbles are skipped, not raised — a response
  with one malformed entry still returns the rest.
- Bus realtime only lights up for vehicles already on the road — usually the
  next imminent departure. Everything else is scheduled times.
- The bus timetable endpoint self-caps its response window (~2 hours of
  departures) regardless of `max_trips`.
- Be respectful: one or two requests per query, no tight polling loops.

## Development

```bash
pip install -e ".[dev]"
pytest                # offline tests only (fixtures, no network)
pytest -m live        # contract tests against the real API — run sparingly
ruff check src tests && mypy src
```

The package version lives in `src/aiotransperth/__init__.py` (`__version__`);
`pyproject.toml` reads it from there, so bump it in one place only.

## License

MIT
