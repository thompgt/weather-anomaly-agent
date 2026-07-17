"""
Orchestrator: for every (station_id, variable) pair present in `readings`,
run both detectors (stl_zscore, s_h_esd) and upsert results into
`anomalies`.

Approach: pull a trailing history window (default 30 days) so STL has
enough context to fit trend/seasonal components reliably, run both
detectors over that whole window, but only *insert* anomalies whose
timestamp falls in the more recent "report" window (default last 7 days).
This mirrors "detect against trailing history, report on what's recent"
from the requirements, and keeps re-runs cheap: older points were already
considered on a prior run, and insert_anomalies_deduped skips anything
already in the table regardless.

Run this on a schedule (cron / Task Scheduler / whatever) to keep
`anomalies` current as new readings land.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

import db
from seasonal_esd import METHOD as ESD_METHOD
from seasonal_esd import seasonal_hybrid_esd
from severity import severity_from_score
from stl_zscore import METHOD as STL_METHOD
from stl_zscore import detect_stl_zscore

HISTORY_DAYS = int(os.environ.get("DETECTION_HISTORY_DAYS", 30))
RECENT_DAYS = int(os.environ.get("DETECTION_RECENT_DAYS", 7))


def _records_from_flagged(flagged, station_id, variable, method):
    return [
        db.AnomalyRecord(
            time=ts.to_pydatetime(),
            station_id=station_id,
            variable=variable,
            value=float(row.value),
            score=float(row.score),
            method=method,
            severity=severity_from_score(row.score),
        )
        for ts, row in flagged.iterrows()
    ]


def run_for_station_variable(
    conn,
    station_id: str,
    variable: str,
    history_days: int = HISTORY_DAYS,
    recent_days: int = RECENT_DAYS,
    source: str = "hourly",
) -> dict[str, int]:
    end = datetime.now(timezone.utc)
    history_start = end - timedelta(days=history_days)
    recent_cutoff = end - timedelta(days=recent_days)

    series_df = db.fetch_series(conn, station_id, variable, history_start, end, source=source)
    if series_df.empty:
        return {"stl_zscore": 0, "s_h_esd": 0}

    inserted_counts = {}

    stl_flagged = detect_stl_zscore(series_df)
    stl_recent = stl_flagged[stl_flagged.index >= recent_cutoff]
    stl_records = _records_from_flagged(stl_recent, station_id, variable, STL_METHOD)
    inserted_counts["stl_zscore"] = db.insert_anomalies_deduped(conn, stl_records)

    esd_flagged = seasonal_hybrid_esd(series_df)
    esd_recent = esd_flagged[esd_flagged.index >= recent_cutoff]
    esd_records = _records_from_flagged(esd_recent, station_id, variable, ESD_METHOD)
    inserted_counts["s_h_esd"] = db.insert_anomalies_deduped(conn, esd_records)

    return inserted_counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run STL/z-score + S-H-ESD detection over all station/variable pairs in readings."
    )
    parser.add_argument("--history-days", type=int, default=HISTORY_DAYS)
    parser.add_argument("--recent-days", type=int, default=RECENT_DAYS)
    parser.add_argument(
        "--source",
        choices=["hourly", "raw"],
        default="hourly",
        help="Pull from readings_hourly continuous aggregate (default) or aggregate raw readings in pandas "
        "(fallback if the continuous aggregate hasn't refreshed yet).",
    )
    args = parser.parse_args()

    conn = db.get_connection()
    try:
        pairs = db.list_station_variables(conn)
        if not pairs:
            print("No (station_id, variable) pairs found in readings -- nothing to do.")
            return

        total_inserted = 0
        for station_id, variable in pairs:
            counts = run_for_station_variable(
                conn,
                station_id,
                variable,
                history_days=args.history_days,
                recent_days=args.recent_days,
                source=args.source,
            )
            n = sum(counts.values())
            total_inserted += n
            print(f"{station_id}/{variable}: stl_zscore={counts['stl_zscore']} s_h_esd={counts['s_h_esd']}")

        print(f"Done. {len(pairs)} station/variable pairs processed, {total_inserted} anomalies inserted.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
