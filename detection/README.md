# detection

Statistical anomaly detection over the `readings` hypertable, writing
flagged points into `anomalies`. Two independent methods run side by side;
both write to the same table so results are comparable/complementary
rather than one replacing the other.

## Methods

### `stl_zscore.py` -- STL decomposition + robust z-score

1. STL-decompose (`statsmodels.tsa.seasonal.STL`, `robust=True`) the hourly
   series into trend + seasonal (period=24h, i.e. daily cycle) + residual.
2. Compute a MAD-based robust z-score on the residual:
   `z = 0.6745 * (residual - median(residual)) / MAD(residual)`.
   MAD is used instead of mean/std so a few genuine anomalies don't blow up
   the spread estimate and hide themselves.
3. Flag points where `|z| >= STL_ZSCORE_THRESHOLD` (default **3.5**).

Good at catching point spikes/drops that break from the recently-learned
trend+seasonal shape.

### `seasonal_esd.py` -- Seasonal Hybrid ESD (S-H-ESD)

Hand-rolled implementation of the method behind Twitter's
`AnomalyDetection` package (Vallis et al. 2014):

1. STL-decompose to get the seasonal component; deseasonalize
   (`value - seasonal`), then center on the **median** rather than the STL
   trend (the "hybrid" part -- more robust to a sustained anomalous run
   dragging the trend line itself).
2. Run a Generalized ESD test (Rosner 1983) on the residual: iteratively
   pull out the most extreme point, test it against a t-distribution-based
   critical value, repeat up to `ESD_MAX_ANOMALY_PCT` (default 10%) of the
   series length. All removals up to the last statistically-significant
   one are flagged.

Generalized ESD accounts for multiple anomalies masking each other (a
single-pass z-score threshold doesn't), and fits daily+yearly seasonal data
like temperature/humidity well.

### `severity.py`

Both methods produce scores that are roughly "robust standard deviations
from expected" in magnitude, so one shared mapping is used:

| `|score|`        | severity |
|-------------------|----------|
| `< 4.0`            | low      |
| `4.0` -- `6.0`      | medium   |
| `>= 6.0`            | high     |

Configurable via `SEVERITY_LOW_MAX` / `SEVERITY_MEDIUM_MAX` env vars.

## Configuration (env vars, all optional)

| Var | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql://weather:weather_dev_password@localhost:5432/weather` | Postgres/TimescaleDB connection string |
| `STL_ZSCORE_THRESHOLD` | `3.5` | flag threshold for `stl_zscore.py` |
| `STL_PERIOD_HOURS` | `24` | STL seasonal period, in hours of hourly data (daily cycle) |
| `ESD_ALPHA` | `0.05` | significance level for the generalized ESD test |
| `ESD_MAX_ANOMALY_PCT` | `0.10` | upper bound on anomalies as a fraction of series length |
| `SEVERITY_LOW_MAX` | `4.0` | score magnitude below this -> `low` |
| `SEVERITY_MEDIUM_MAX` | `6.0` | score magnitude below this -> `medium`, else `high` |
| `DETECTION_HISTORY_DAYS` | `30` | trailing history window `run.py` fits detectors on |
| `DETECTION_RECENT_DAYS` | `7` | only points in this recent window get inserted per run |

Set these in the repo-root `.env` (see `.env.example`); all scripts load it
via `python-dotenv`.

## Running

```bash
cd detection
pip install -r requirements.txt

# One-off, single station/variable, prints results without writing (useful for tuning thresholds):
python stl_zscore.py --station-id station_01 --variable temperature_c --days 30 --dry-run
python seasonal_esd.py --station-id station_01 --variable temperature_c --days 30 --dry-run

# Same, but actually write to `anomalies`:
python stl_zscore.py --station-id station_01 --variable temperature_c --days 30
python seasonal_esd.py --station-id station_01 --variable temperature_c --days 30

# Orchestrated run: every (station_id, variable) pair currently in `readings`,
# both methods, writes new anomalies (existing (time, station_id, variable, method)
# rows are skipped -- safe to re-run, e.g. from cron/Task Scheduler on an interval):
python run.py
```

`run.py` fits each detector on a 30-day trailing history window (enough
context for STL to learn trend/seasonal shape) but only inserts anomalies
whose timestamp falls in the last 7 days, so repeated runs stay cheap and
don't re-litigate old history. `insert_anomalies_deduped` in `db.py` is the
dedup safety net regardless, since the shared schema has no unique
constraint on `(time, station_id, variable, method)` to enforce it at the
DB level.

If `readings_hourly` (the continuous aggregate) hasn't refreshed yet, pass
`--source raw` to `run.py` to aggregate straight from `readings` in pandas
instead.

## Backtest

```bash
python backtest.py
```

Sanity-checks the pipeline against a real documented event: the **2021
Pacific Northwest heat dome** (Portland, OR hit an all-time record 116F /
46.7C on 2021-06-28, versus a prior record of 107F -- see
[NWS Portland climate records](https://www.weather.gov/pqr/PortlandClimateRecords)).
Event window: 2021-06-25 to 2021-06-29.

- If `readings` already has backfilled history for a station whose id
  suggests the Pacific Northwest (contains `portland`/`pdx`/`seattle`/`sea`/`pnw`),
  it runs detection on that real data.
- Otherwise (likely, until ingestion backfills historical data) it falls
  back to a **clearly-labeled synthetic** hourly series: a normal diurnal +
  seasonal late-June PNW temperature pattern with an injected heat-dome
  spike (~28C normal high -> ~46C synthetic peak) over the event window.
  This validates pipeline mechanics, not real-world detection recall.

It reports how many points each method flagged inside the event window and
exits non-zero if neither method caught it. This is a smoke test, not an
evaluation -- no precision/recall is computed.

Force a mode explicitly with `--source real` or `--source synthetic`.
