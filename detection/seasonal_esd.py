"""
Seasonal Hybrid ESD (S-H-ESD) anomaly detection.

Hand-rolled implementation of the method behind Twitter's
AnomalyDetection package (Vallis, Hochenbaum, Kejariwal 2014), since a
maintained "adtk"/"seasonal-esd" package isn't a hard dependency here and
the algorithm is compact:

1. STL-decompose the series to pull out the seasonal component (daily
   cycle, period=24 for hourly data).
2. Deseasonalize: residual_i = value_i - seasonal_i - median(value - seasonal).
   Using the median (not the STL trend) as the robust "center" is the
   "hybrid" part of S-H-ESD -- it tolerates the trend line itself being
   dragged around by an anomalous run, which plain STL-residual detection
   (stl_zscore.py) is more exposed to for short bursts.
3. Run a Generalized ESD test (Rosner 1983) on the residual: iteratively
   find the most extreme point (max |x - mean| / std), test it against a
   critical value derived from the t-distribution, and remove it; repeat up
   to `max_anomalies` times. All points removed up to and including the
   last iteration whose test statistic exceeded its critical value are
   flagged as anomalies.

Generalized ESD is a good fit here because -- unlike a single z-score
threshold -- it accounts for the fact that removing k anomalies from a
sample changes the sample's own mean/std, so it doesn't lose power when
there are multiple anomalies masking each other.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.seasonal import STL

from severity import severity_from_score

METHOD = "s_h_esd"

ESD_ALPHA = float(os.environ.get("ESD_ALPHA", 0.05))
# Cap how many points can be flagged, as a fraction of series length --
# generalized ESD needs an upper bound k on anomaly count going in.
ESD_MAX_ANOMALY_PCT = float(os.environ.get("ESD_MAX_ANOMALY_PCT", 0.10))
STL_PERIOD = int(os.environ.get("STL_PERIOD_HOURS", 24))
MIN_POINTS = STL_PERIOD * 2


def generalized_esd_test(
    x: np.ndarray, max_anomalies: int, alpha: float = 0.05
) -> list[tuple[int, float]]:
    """
    Rosner's generalized ESD test.

    Returns a list of (index_into_x, score) for points flagged as
    anomalous, where score = R_i / lambda_i (>= 1.0 means "significant"
    at this iteration; larger = more extreme relative to the critical
    value, used downstream as the anomaly score).
    """
    n = len(x)
    if n < 3 or max_anomalies < 1:
        return []

    working = x.astype(float).copy()
    working_idx = np.arange(n)
    results: list[tuple[int, float, float]] = []  # (original_idx, R, lambda)

    k = min(max_anomalies, n - 2)
    for i in range(1, k + 1):
        mean = working.mean()
        std = working.std(ddof=1)
        if std == 0 or np.isnan(std):
            break
        abs_dev = np.abs(working - mean)
        max_pos = int(np.argmax(abs_dev))
        R = abs_dev[max_pos] / std

        n_i = n - i + 1
        p = 1 - alpha / (2 * n_i)
        t_crit = stats.t.ppf(p, n_i - 2)
        lam = (n_i - 1) * t_crit / np.sqrt((n_i - 2 + t_crit**2) * n_i)

        results.append((int(working_idx[max_pos]), float(R), float(lam)))

        working = np.delete(working, max_pos)
        working_idx = np.delete(working_idx, max_pos)

    # Largest i where R_i > lambda_i: all removals up to (and including)
    # that iteration are genuine anomalies.
    last_significant = -1
    for i, (_, R, lam) in enumerate(results):
        if R > lam:
            last_significant = i

    flagged = []
    for i in range(last_significant + 1):
        idx, R, lam = results[i]
        flagged.append((idx, R / lam))
    return flagged


def seasonal_hybrid_esd(
    df: pd.DataFrame,
    period: int = STL_PERIOD,
    alpha: float = ESD_ALPHA,
    max_anomaly_pct: float = ESD_MAX_ANOMALY_PCT,
) -> pd.DataFrame:
    """
    df: DataFrame indexed by time (regular hourly cadence), with a
        'value' column. See db.fetch_series.

    Returns a DataFrame with columns: value, residual, score -- one row
    per point flagged as anomalous.
    """
    series = df["value"].dropna()
    if len(series) < MIN_POINTS:
        return pd.DataFrame(columns=["value", "residual", "score"])

    stl = STL(series, period=period, robust=True)
    seasonal = stl.fit().seasonal
    deseasonalized = series - seasonal
    residual = deseasonalized - deseasonalized.median()

    max_anomalies = max(1, int(len(series) * max_anomaly_pct))
    flagged = generalized_esd_test(residual.to_numpy(), max_anomalies, alpha=alpha)
    if not flagged:
        return pd.DataFrame(columns=["value", "residual", "score"])

    idxs = [i for i, _ in flagged]
    scores = {series.index[i]: s for i, s in flagged}
    out = pd.DataFrame(
        {
            "value": series.iloc[idxs],
            "residual": residual.iloc[idxs],
        }
    )
    out["score"] = [scores[ts] for ts in out.index]
    # Sign the score with the direction of deviation so severity/consumers
    # can tell "spike" from "drop" the same way stl_zscore's z-score does.
    out["score"] = out["score"] * np.sign(out["residual"]).replace(0, 1)
    return out.sort_index()


def _run_cli() -> None:
    import db

    parser = argparse.ArgumentParser(description="Run Seasonal Hybrid ESD detection.")
    parser.add_argument("--station-id", required=True)
    parser.add_argument("--variable", required=True)
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days.")
    parser.add_argument("--alpha", type=float, default=ESD_ALPHA)
    parser.add_argument("--dry-run", action="store_true", help="Print flagged points, don't write to DB.")
    args = parser.parse_args()

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)

    conn = db.get_connection()
    try:
        series_df = db.fetch_series(conn, args.station_id, args.variable, start, end)
        flagged = seasonal_hybrid_esd(series_df, alpha=args.alpha)
        if flagged.empty:
            print(f"No anomalies flagged for {args.station_id}/{args.variable}.")
            return

        records = [
            db.AnomalyRecord(
                time=ts.to_pydatetime(),
                station_id=args.station_id,
                variable=args.variable,
                value=float(row.value),
                score=float(row.score),
                method=METHOD,
                severity=severity_from_score(row.score),
            )
            for ts, row in flagged.iterrows()
        ]

        if args.dry_run:
            for r in records:
                print(f"{r.time}  value={r.value:.2f}  score={r.score:.2f}  severity={r.severity}")
            print(f"({len(records)} points flagged, dry-run: not written)")
        else:
            inserted = db.insert_anomalies_deduped(conn, records)
            print(f"Flagged {len(records)} points, inserted {inserted} new rows (rest were dupes).")
    finally:
        conn.close()


if __name__ == "__main__":
    _run_cli()
