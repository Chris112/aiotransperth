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
  status, car count. Plus which way each one is going, and whether it reaches
  where you're actually headed.

Async (`aiohttp` is the only dependency), fully typed, Python 3.12+, MIT.

## Getting started

```bash
pip install aiotransperth
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

## Which way is my train going?

The live payload says where a service *terminates*, never which way it's
heading — so at a through-station like Edgewater, "the next train" is a
coin flip between the city and Yanchep. `serves_journey` answers the question
people actually ask:

```python
from aiotransperth import serves_journey

# A train showing "Perth" gets you from Edgewater to the city.
serves_journey("Yanchep Line", "Edgewater Stn", "Perth", "Perth Underground Stn")
# True

# One showing "Yanchep" does not.
serves_journey("Yanchep Line", "Edgewater Stn", "Yanchep", "Perth Underground Stn")
# False

# Short-workings are kept for the stations they reach, and only those:
serves_journey("Yanchep Line", "Edgewater Stn", "Clarkson", "Joondalup Stn")  # True
serves_journey("Yanchep Line", "Edgewater Stn", "Clarkson", "Butler Stn")     # False
```

Filtering a station's departures to one journey is then a one-liner:

```python
trains = await client.get_train_departures("Yanchep Line", "Edgewater Stn")
mine = [t for t in trains
        if serves_journey("Yanchep Line", "Edgewater Stn", t.destination, "Perth Underground Stn")]
```

This works off a route-ordered station table generated from Transperth's own
timetable (`scripts/generate_line_order.py`), so it needs no network call.
Check `is_known_journey` first if your station names come from stored config —
the table is a snapshot, and the network occasionally gains a station.

Two things that bite if you assume otherwise: not every line is city-radial
(the Airport Line runs High Wycombe → CBD → Claremont, so the city sits
mid-route), and a terminus naming no station on the line — a bare `"Perth"`,
or somewhere on another line — means the service ends its run with this line
at the CBD.

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
  stations = await client.get_train_stations("Midland Line")  # just that line's
  ```

  Or skip the network entirely and read the built-in table, which has the
  bonus of being in route order rather than alphabetical:

  ```python
  from aiotransperth import known_lines, line_stations

  known_lines()                    # ("Airport Line", ..., "Yanchep Line")
  line_stations("Yanchep Line")    # ("Elizabeth Quay Stn", ..., "Yanchep Stn")
  ```

## API

All methods are coroutines on `TransperthClient`. Construct it bare (it
manages its own `aiohttp` session as an async context manager) or pass your
own session, which will not be closed for you.

| Method | Returns | Notes |
|---|---|---|
| `get_stop_timetable(stop_code, *, when=None, max_trips=100)` | `StopTimetable` (stop + `BusDeparture` tuple) | Realtime always requested. `when` defaults to now (Perth). |
| `validate_stop(stop_code)` | `Stop` | Raises `InvalidStopError` for unknown codes. |
| `get_route_trips(route, *, mode="bus", when=None, max_options=4)` | `tuple[RouteTrip, ...]` | Upcoming trips for a route, e.g. `"414"`. `mode="rail"` takes a line name and returns services running it end to end. |
| `get_trip_stops(trip)` | `tuple[TripStop, ...]` | Every stop on a trip, with times, boarding flags, GPS. |
| `get_train_departures(line, station)` | `tuple[TrainDeparture, ...]` | Live status; raises `InvalidStopError` for unknown stations. |
| `get_train_lines()` | `tuple[str, ...]` | The 8 line names. Fetched once, cached per client. |
| `get_train_stations(line=None)` | `tuple[TrainStation, ...]` | All ~80 stations, or one line's. Fetched once each, cached per client. |

These need no client and no network — they read the generated table:

| Function | Returns | Notes |
|---|---|---|
| `serves_journey(line, station, terminus, target)` | `bool` | Whether a service terminating at `terminus` carries you `station`→`target`. |
| `is_known_journey(line, station, target)` | `bool` | Whether both stations are in the table. Check before trusting stored names. |
| `line_stations(line)` | `tuple[str, ...]` | The line in route order, city end first. |
| `line_endpoints(line)` | `tuple[str, str]` | Its two end stations. |
| `known_lines()` | `tuple[str, ...]` | Lines the table covers. |

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

`_line_data.py` is generated — regenerate it when Metronet opens a line:

```bash
python scripts/generate_line_order.py > src/aiotransperth/_line_data.py
```

It costs about three requests per line and caches to disk, so a re-run after
a failure is cheap. Space requests generously: an earlier version crawled
every station on every line and got the whole IP rate-limited for five and a
half hours.

## License

MIT
