# aiotransperth

Async Python client for Transperth (Perth, WA) bus and train departures,
with realtime delay data. Uses Transperth's unofficial website APIs — the
only channel that carries Perth realtime data (no public GTFS-Realtime
exists).

## Install

```bash
pip install aiotransperth
```

## Usage

```python
import asyncio
from aiotransperth import TransperthClient


async def main() -> None:
    async with TransperthClient() as client:
        # Buses: next departures at a stop (realtime included)
        timetable = await client.get_stop_timetable("12627")
        for dep in timetable.departures:
            print(dep.route, dep.scheduled, dep.delay_minutes, dep.live.description)

        # Trains: live status for a station on a line
        trains = await client.get_train_departures("Midland Line", "Maylands Stn")
        for train in trains:
            print(train.destination, train.platform, train.estimated)


asyncio.run(main())
```

All datetimes are timezone-aware `Australia/Perth`. Errors raise typed
exceptions (`RateLimitError`, `AuthError`, `NetworkError`,
`InvalidStopError`). The client never sleeps or retries (beyond one token
refresh); back-off policy belongs to the caller.

Be respectful of Transperth's infrastructure: their rate limit (HTTP 429)
has a sticky cooldown shared with the public website.
