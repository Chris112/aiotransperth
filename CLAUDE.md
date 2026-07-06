# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`aiotransperth` — async Python client (aiohttp, Python 3.12+) for Transperth's **unofficial** website APIs, the only channel carrying Perth realtime bus/train data. Because the API is unofficial, response shapes are pinned by live contract tests rather than a spec.

## Commands

A `.venv` exists at the repo root (Python 3.14). Dev setup: `pip install -e ".[dev]"`.

```bash
pytest                                    # offline tests only (fixtures via aioresponses; live tests deselected via addopts)
pytest tests/test_client_bus.py           # one file
pytest tests/test_models.py -k delay      # one test by keyword
pytest -m live                            # contract tests against the REAL API — run sparingly, never in loops
ruff check src tests
mypy src                                  # strict mode
```

**Live-test caution:** Transperth's HTTP 429 cooldown is sticky (>60 s) and shared with their public website. Don't re-run `-m live` in tight iteration; CI never runs it.

**Dev dependency pin:** `aiohttp<3.14` is constrained in the `dev` extra only, because aioresponses 0.7.9 can't mock aiohttp ≥3.14. Runtime stays `aiohttp>=3.9`. Don't "fix" this by bumping either side without checking aioresponses compatibility.

## Architecture

Single package `src/aiotransperth/`, all public API re-exported from `__init__.py` (keep `__all__` in sync — `tests/test_public_api.py` checks it).

Two distinct API families, both behind one `TransperthClient` (`client.py`):

- **Bus (SilverRail endpoints)** — form-POSTs requiring a CSRF token. `auth.py` owns this: tokens are scoped per `AuthContext` (ROUTE vs STOP — different ModuleId/TabId headers and issuing pages; using the wrong one gets HTTP 401). `TokenManager` caches one token per context, scraped by regex from the issuing HTML page. `_bus_post` retries exactly once on 401 after invalidating the token — that is the client's *only* retry; it never sleeps, and back-off policy deliberately belongs to the caller.
- **Train** — plain GETs with static headers (`const.py`), no token. Line/station catalogs have no JSON endpoint; `stations.py` regex-parses the server-rendered dropdowns on the Live Train Times page.

`models.py` holds frozen slotted dataclasses plus the time-parsing rules. All API times are naive Perth-local strings; **every datetime this library emits must be timezone-aware `Australia/Perth`** (`PERTH_TZ`). `parse_clock_near` anchors bare clock strings ("1:48pm") to a reference datetime and rolls forward a day for just-past-midnight displays; it returns `None` for unparseable text because the API puts status strings in time fields. Parsing is lenient by design: malformed trip entries are skipped, missing fields default to `""`/`None`.

All errors subclass `TransperthError` (`exceptions.py`): `RateLimitError` (429), `AuthError` (token issues, bus only), `NetworkError` (wraps `aiohttp.ClientError`), `InvalidStopError` (bad stop code / station name — trains signal this via "check spelling" text in the response, not a status code).

## Tests

Offline tests mock HTTP with `aioresponses` against captured payloads in `tests/fixtures/`. If the real API changes shape, update the fixture *and* verify with `pytest -m live` (`tests/live/test_contract.py`, fixed inputs: bus 414, stop 12627, Maylands Stn). pytest-asyncio runs in `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed.
