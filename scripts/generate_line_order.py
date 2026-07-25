"""Regenerate the route-ordered station table in `aiotransperth/_line_data.py`.

Transperth publishes no station ordering: the dropdowns are alphabetical and
station IDs encode nothing. But the SilverRail timetable does — asking it for
a train line's trips with `Mode=rail` returns services that run the line end
to end, and a trip's stop list is that line in route order.

Run:

    python scripts/generate_line_order.py > src/aiotransperth/_line_data.py

Costs about three requests per line. An earlier version crawled every station
on every line (~130 requests) and got the whole IP rate-limited for five and a
half hours; Transperth's 429 cooldown is sticky and shared with their public
website, so requests are spaced and results cached to disk.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from collections import defaultdict
from datetime import timedelta
from itertools import pairwise
from pathlib import Path

from aiotransperth import RateLimitError, TransperthClient, TransperthError
from aiotransperth.const import CBD_STATIONS

REQUEST_SPACING = 4.0
RATE_LIMIT_COOLDOWN = 180.0
MAX_ATTEMPTS = 3
MAX_TRIPS_PER_LINE = 3
CACHE_PATH = Path(__file__).with_name(".line_order_cache.json")

# Trip stops carry the boarding point: "Edgewater Stn Platform 1".
_PLATFORM_RE = re.compile(r"\s+Platform\s+\S+$", re.IGNORECASE)


def _station_name(stop_description: str) -> str:
    return _PLATFORM_RE.sub("", stop_description).strip()


def _topological_order(sequences: list[list[str]]) -> list[str]:
    """Merge consistently-oriented station sequences into one total order.

    Raises ValueError when the sequences disagree (a cycle), which means the
    orientation step upstream got something wrong.
    """
    successors: dict[str, set[str]] = defaultdict(set)
    predecessors: dict[str, set[str]] = defaultdict(set)
    nodes: set[str] = set()
    for seq in sequences:
        nodes.update(seq)
        for first, second in pairwise(seq):
            if second not in successors[first]:
                successors[first].add(second)
                predecessors[second].add(first)

    # Deterministic Kahn: break ties alphabetically so reruns are stable.
    ready = sorted(n for n in nodes if not predecessors[n])
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for nxt in sorted(successors[node]):
            predecessors[nxt].discard(node)
            if not predecessors[nxt]:
                ready.append(nxt)
        ready.sort()
    if len(order) != len(nodes):
        raise ValueError(
            f"station sequences form a cycle; ordered {len(order)} of {len(nodes)}"
        )
    return order


def _orient(sequences: list[list[str]]) -> list[list[str]]:
    """Flip sequences running opposite to the longest one."""
    ordered = sorted(sequences, key=len, reverse=True)
    reference = ordered[0]
    position = {station: i for i, station in enumerate(reference)}
    oriented = [reference]
    for seq in ordered[1:]:
        shared = [s for s in seq if s in position]
        if len(shared) < 2:
            print(f"  ! ignoring trip with too little overlap: {seq}", file=sys.stderr)
            continue
        forward = position[shared[-1]] > position[shared[0]]
        oriented.append(seq if forward else seq[::-1])
    return oriented


def _is_subsequence(seq: list[str], order: list[str]) -> bool:
    it = iter(order)
    return all(station in it for station in seq)


def _load_cache() -> dict[str, list[list[str]]]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


async def _with_backoff(coro_factory, label: str):
    """Await `coro_factory()`, waiting out rate limits rather than failing."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        await asyncio.sleep(REQUEST_SPACING)
        try:
            return await coro_factory()
        except RateLimitError:
            wait = RATE_LIMIT_COOLDOWN * attempt
            print(
                f"  · rate limited on {label}, waiting {wait:.0f}s "
                f"(attempt {attempt}/{MAX_ATTEMPTS})",
                file=sys.stderr,
            )
            await asyncio.sleep(wait)
    raise TransperthError(f"{label}: still rate limited after {MAX_ATTEMPTS} attempts")


async def _line_sequences(
    client: TransperthClient, cache: dict[str, list[list[str]]], line: str
) -> list[list[str]]:
    """Station sequences for `line`, one per sampled trip."""
    if line in cache:
        print(f"{line}: cached", file=sys.stderr)
        return [list(seq) for seq in cache[line]]

    trips = await _with_backoff(
        lambda: client.get_route_trips(line, mode="rail", max_options=8),
        f"{line} trips",
    )
    if not trips:
        raise ValueError(f"{line}: no rail trips returned; check the line name")

    # Longest-running trips first — they're the ones covering the whole line.
    def _duration(trip) -> timedelta:
        if trip.start_time and trip.finish_time:
            return trip.finish_time - trip.start_time
        return timedelta(0)

    ranked = sorted(trips, key=_duration, reverse=True)

    sequences: list[list[str]] = []
    for trip in ranked[:MAX_TRIPS_PER_LINE]:
        stops = await _with_backoff(
            lambda t=trip: client.get_trip_stops(t), f"{line} trip stops"
        )
        names = [_station_name(s.name) for s in stops]
        if len(names) >= 2:
            sequences.append(names)
            print(f"  {len(names)} stops: {names[0]} → {names[-1]}", file=sys.stderr)
        # One full-line trip is usually enough; stop as soon as a later trip
        # adds nothing new.
        if len(sequences) >= 2 and set(sequences[-1]) <= set(sequences[0]):
            break

    if not sequences:
        raise ValueError(f"{line}: no trip returned a usable stop list")
    cache[line] = sequences
    CACHE_PATH.write_text(json.dumps(cache))
    return sequences


def _canonicalise(names: list[str], catalog: set[str], line: str) -> list[str]:
    """Map trip stop names onto the live-status catalog's spelling.

    The two endpoints disagree: a trip stop says "Mciver Stn" and "Cockburn
    Stn" where the station dropdown says "McIver Stn" and "Cockburn Central
    Stn". Only the dropdown's spelling works for live departures, so the table
    must store that — a mismatch would make a station unqueryable.
    """
    by_base = {station.removesuffix(" Stn").casefold(): station for station in catalog}
    resolved = []
    for name in names:
        base = name.removesuffix(" Stn").casefold()
        if base in by_base:
            resolved.append(by_base[base])
            continue
        matches = sorted(
            {full for key, full in by_base.items() if key.startswith(base)}
        )
        if len(matches) == 1:
            print(f"  · {name} → {matches[0]}", file=sys.stderr)
            resolved.append(matches[0])
        elif matches:
            raise ValueError(f"{line}: {name!r} matches several stations: {matches}")
        else:
            raise ValueError(
                f"{line}: {name!r} matches no station in the live-times catalog"
            )
    return resolved


async def _line_order(
    client: TransperthClient, cache: dict[str, list[list[str]]], line: str
) -> list[str]:
    print(f"{line}:", file=sys.stderr)
    sequences = await _line_sequences(client, cache, line)

    full_catalog = {
        s.name
        for s in await _with_backoff(client.get_train_stations, "station catalog")
    }
    line_catalog = {
        s.name
        for s in await _with_backoff(
            lambda: client.get_train_stations(line), f"{line} station catalog"
        )
    }
    # The site's per-line page filters by line name, except where it doesn't:
    # "Yanchep Line" returns 16 stations but "Thornlie-Cockburn Line" returns
    # the whole network, apparently tripped up by the hyphen. Detect that
    # rather than reporting every station on the network as uncovered.
    filtered = line_catalog != full_catalog

    # Station names are unique network-wide, so resolve against the full list.
    sequences = [_canonicalise(seq, full_catalog, line) for seq in sequences]

    oriented = _orient(sequences)
    order = _topological_order(oriented)

    # The safety net: if every sampled trip really runs along this order, the
    # order is right. A violation means the merge is wrong, not merely odd.
    for seq in oriented:
        if not _is_subsequence(seq, order):
            raise ValueError(f"{line}: {seq} is not a subsequence of {order}")

    # Not every line is city-radial — the Airport Line runs through the CBD and
    # out to Claremont — so the city may sit mid-route. Orientation is only
    # cosmetic (`serves_journey` works off relative positions), but pointing
    # index 0 at the end nearer the CBD keeps the table readable. A line with
    # no CBD station at all would break the through-routing fallback in
    # lines.py, so that fails loudly.
    cbd = next((i for i, s in enumerate(order) if s in CBD_STATIONS), None)
    if cbd is None:
        raise ValueError(
            f"{line}: no CBD station in {order}; update CBD_STATIONS in const.py"
        )
    if cbd > len(order) - 1 - cbd:
        order.reverse()

    # A trip that skips stations (an express run) would leave holes. Report
    # them rather than shipping a line that silently can't route to them.
    if filtered:
        uncovered = sorted(line_catalog - set(order))
        if uncovered:
            print(
                f"  ! not on the sampled trips: {', '.join(uncovered)}",
                file=sys.stderr,
            )
    else:
        print(
            "  · per-line station list unavailable; coverage unchecked", file=sys.stderr
        )
    return order


async def main() -> None:
    cache = _load_cache()
    async with TransperthClient() as client:
        lines = await _with_backoff(client.get_train_lines, "line catalog")
        orders = {line: await _line_order(client, cache, line) for line in lines}

    print('"""Route-ordered stations per train line.')
    print()
    print("Generated by scripts/generate_line_order.py — do not edit by hand.")
    print("Index 0 is the end nearer the CBD.")
    print('"""')
    print()
    print("from __future__ import annotations")
    print()
    print("LINE_STATIONS: dict[str, tuple[str, ...]] = {")
    for line, order in orders.items():
        print(f"    {line!r}: (")
        for station in order:
            print(f"        {station!r},")
        print("    ),")
    print("}")


if __name__ == "__main__":
    asyncio.run(main())
