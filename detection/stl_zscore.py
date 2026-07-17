"""
STL decomposition + robust (MAD-based) z-score anomaly detection.

Method
------
1. Decompose the series into trend + seasonal + residual via statsmodels'
   STL (Seasonal-Trend decomposition using LOESS).
2. Compute a robust z-score on the residual using the median absolute
   deviation (MAD) instead of mean/std, so a handful of genuine anomalies
   don't inflate the spread and mask themselves (or each other):

       z_i = 0.6745 * (residual_i - median(residual)) / MAD(residual)

   The 0.6745 constant makes MAD-based z comparable to a standard z-score
   under a normal distribution.
3. Flag any point with |z| >= STL_ZSCORE_THRESHOLD (default 3.5, i.e.
   roughly the "very unlikely under normality" region, chosen a bit looser
   than the classic 3.0 to keep hourly weather noise from over-triggering).

Seasonality period defaults to 24 (hourly data, daily cycle) since that's
the dominant cycle in temperature/humidity/pressure and detection runs off
the readings_hourly continuous aggregate.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

from severity import severity_from_score

METHOD = "stl_zscore"

ZSCORE_THRESHOLD = float(os.environ.get("STL_ZSCORE_THRESHOLD", 3.5))
STL_PERIOD = int(os.environ.get("STL_PERIOD_HOURS", 24))
# STL needs at least ~2 full periods to fit a seasonal component.
MIN_POINTS = STL_PERIOD * 2


def robust_zscore(residual: pd.Series) -> pd.Series:
    median = residual.median()
    mad = (residual - median).abs().median()
    if mad == 0 or np.isnan(mad):
        # Degenerate/flat residual: fall back to std, and if that's also
        # zero everything is exactly on trend -- no anomalies possible.
        std = residual.std()
        if std == 0 or np.isnan(std):
            return pd.Series(0.0, index=residual.index)
        return (residual - residual.mean()) / std
    return 0.6745 * (residual - median) / mad


def detect_stl_zscore(
    df: pd.DataFrame,
    threshold: float = ZSCORE_THRESHOLD,
    period: int = STL_PERIOD,
) -> pd.DataFrame:
    """
    df: DataFrame indexed by time (regular hourly cadence), with a
        'value' column. See db.fetch_series.

    Returns a DataFrame (subset of input index) with columns:
        value, residual, score  -- for points where |score| >= threshold.
    """
    series = df["value"].dropna()
    if len(series) < MIN_POINTS:
        return pd.DataFrame(columns=["value", "residual", "score"])

    stl = STL(series, period=period, robust=True)
    result = stl.fit()
    residual = result.resid
    z = robust_zscore(residual)

    flagged = z.abs() >= threshold
    out = pd.DataFrame(
        {
            "value": series[flagged],
            "residual": residual[flagged],
            "score": z[flagged],
        }
    )
    return out


def _run_cli() -> None:
    import db

    parser = argparse.ArgumentParser(description="Run STL + robust z-score detection.")
    parser.add_argument("--station-id", required=True)
    parser.add_argument("--variable", required=True)
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days.")
    parser.add_argument("--threshold", type=float, default=ZSCORE_THRESHOLD)
    parser.add_argument("--dry-run", action="store_true", help="Print flagged points, don't write to DB.")
    args = parser.parse_args()

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)

    conn = db.get_connection()
    try:
        series_df = db.fetch_series(conn, args.station_id, args.variable, start, end)
        flagged = detect_stl_zscore(series_df, threshold=args.threshold)
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
