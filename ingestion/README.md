# ingestion

Fetches weather data from [Open-Meteo](https://open-meteo.com) (no API key
needed) and upserts it into the shared `readings` TimescaleDB hypertable
defined in `infra/schema.sql`.

```
openmeteo.py   shared request/validate/normalize logic (used by both scripts below)
fetch.py       one-shot: current + recent data, via the forecast API
backfill.py    one-shot: historical data over a date range, via the archive API
scheduler.py   runs fetch.py on a repeating interval (APScheduler)
db.py          psycopg connection + upsert helpers
config.py      stations, variable mapping, env-driven settings
test_smoke.py  no-network/no-DB sanity check of the normalization logic
```

Variables collected: `temperature_c`, `humidity_pct`, `wind_speed_ms`,
`pressure_hpa` — matching the units documented in `schema.sql` (units are
normalized at request time via Open-Meteo's `temperature_unit`/
`wind_speed_unit` params; humidity and surface pressure are already `%`
and `hPa`).

Stations are hardcoded in `config.py` as three example locations — Denver
CO, Miami FL, Seattle WA — chosen to cover distinct climates (arid, humid
subtropical, marine) for a more interesting anomaly-detection MVP. Override
by editing `STATIONS` in `config.py`, or by setting the `STATIONS_JSON` env
var to a JSON array of `{"id", "name", "lat", "lon"}` objects.

## Setup

From the repo root:

```bash
cp .env.example .env        # if not already done; fill in DATABASE_URL
pip install -r ingestion/requirements.txt
```

`ingestion/` reads `DATABASE_URL` from the environment (via `.env` at the
repo root, loaded with python-dotenv). Make sure TimescaleDB is up and the
schema applied:

```bash
cd infra && docker compose up -d db
psql "$DATABASE_URL" -f schema.sql   # applied automatically on first db boot too
```

All commands below are run **from the repo root** (so relative imports and
`.env` discovery work):

## Backfill (run once, before detection can build a baseline)

```bash
python -m ingestion.backfill
# or a custom range:
python -m ingestion.backfill --start 2023-01-01 --end 2025-12-31
```

Defaults: `--start` from `BACKFILL_START_DATE` env var (default
`2015-01-01`), `--end` defaults to yesterday. Open-Meteo's archive API has
a short reporting lag, so "yesterday" is normally the latest safe date.

## Live fetch (single run)

```bash
python -m ingestion.fetch
```

Fetches `FETCH_PAST_DAYS` days of past data (default 2, to backfill any
gap since the last run) plus the current forecast day, per station.

## Scheduler (long-running process)

```bash
python -m ingestion.scheduler
```

Runs `fetch.py`'s job immediately, then every `FETCH_INTERVAL_MINUTES`
(default 30). If the database is unreachable when a cycle runs, the
failure is logged and the row batch is skipped — the process keeps running
and retries on the next interval rather than crashing.

## Config (environment variables)

| Variable                  | Default                                            | Purpose                                   |
|----------------------------|-----------------------------------------------------|--------------------------------------------|
| `DATABASE_URL`             | (from `.env.example`)                              | TimescaleDB connection string              |
| `STATIONS_JSON`            | unset (uses hardcoded 3 stations)                  | override station list                      |
| `FETCH_INTERVAL_MINUTES`   | `30`                                                | scheduler.py interval                      |
| `FETCH_PAST_DAYS`          | `2`                                                 | fetch.py lookback window                   |
| `BACKFILL_START_DATE`      | `2015-01-01`                                       | backfill.py default start date             |
| `REQUEST_TIMEOUT_SECONDS`  | `30`                                                | Open-Meteo HTTP timeout                    |
| `DB_RETRIES`               | `3`                                                 | connection attempts before giving up       |
| `DB_RETRY_DELAY_SECONDS`   | `5`                                                 | delay between connection retries           |

## Smoke test

```bash
python -m ingestion.test_smoke
```

Mocks the Open-Meteo HTTP response and checks that normalization produces
the expected rows (unit handling, null-skipping, variable naming) — no
network or database required.
