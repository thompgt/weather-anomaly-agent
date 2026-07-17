"""
Read-only(ish) DB helpers for the API layer.

Reads DATABASE_URL from the environment (python-dotenv, same convention as
ingestion/db.py, detection/db.py, agent/db.py). Uses plain psycopg (sync),
one connection per call, matching the style of the other components rather
than introducing a new pooling dependency.
"""

from __future__ import annotations

import os
from datetime import datetime

import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://weather:weather_dev_password@localhost:5432/weather"
)


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def fetch_timeseries(
    station_id: str, variable: str, start: datetime, end: datetime
) -> tuple[str, list[dict]]:
    """
    Hourly-aggregated time series for a station+variable in [start, end].

    Reads readings_hourly (the continuous aggregate) first. If it comes back
    empty -- e.g. fresh ingestion before the first continuous-aggregate
    refresh policy run -- falls back to aggregating straight from `readings`
    in SQL, same pattern as detection/db.py's fetch_series(source="raw").

    Returns (source, rows) where source is "readings_hourly" or "readings".
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT bucket AS time, avg_value, min_value, max_value, sample_count
            FROM readings_hourly
            WHERE station_id = %s AND variable = %s
              AND bucket >= %s AND bucket <= %s
            ORDER BY bucket;
            """,
            (station_id, variable, start, end),
        )
        rows = cur.fetchall()
        if rows:
            cols = ["time", "avg_value", "min_value", "max_value", "sample_count"]
            return "readings_hourly", [dict(zip(cols, row)) for row in rows]

        cur.execute(
            """
            SELECT time_bucket('1 hour', time) AS time,
                   avg(value) AS avg_value,
                   min(value) AS min_value,
                   max(value) AS max_value,
                   count(*) AS sample_count
            FROM readings
            WHERE station_id = %s AND variable = %s
              AND time >= %s AND time <= %s
            GROUP BY 1
            ORDER BY 1;
            """,
            (station_id, variable, start, end),
        )
        rows = cur.fetchall()
        cols = ["time", "avg_value", "min_value", "max_value", "sample_count"]
        return "readings", [dict(zip(cols, row)) for row in rows]


def fetch_anomalies(
    status: str | None = None,
    severity: str | None = None,
    station_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 200,
) -> list[dict]:
    """Same filter semantics as agent/db.py's get_anomalies: optional
    status/severity/station_id/time-range filters, newest first."""
    clauses = []
    params: list = []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if severity:
        clauses.append("severity = %s")
        params.append(severity)
    if station_id:
        clauses.append("station_id = %s")
        params.append(station_id)
    if start:
        clauses.append("time >= %s")
        params.append(start)
    if end:
        clauses.append("time <= %s")
        params.append(end)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, time, window_end, station_id, variable, value, score,
                   method, severity, status, agent_note, created_at
            FROM anomalies
            {where}
            ORDER BY time DESC
            LIMIT %s;
            """,
            params,
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_anomalies_since(since_id: int, limit: int = 100) -> list[dict]:
    """Anomalies with id > since_id, oldest first -- used to poll for newly
    inserted rows for the live feed."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, time, window_end, station_id, variable, value, score,
                   method, severity, status, agent_note, created_at
            FROM anomalies
            WHERE id > %s
            ORDER BY id ASC
            LIMIT %s;
            """,
            (since_id, limit),
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def max_anomaly_id() -> int:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(id), 0) FROM anomalies;")
        (max_id,) = cur.fetchone()
        return max_id


def fetch_reports(limit: int = 100) -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, period_start, period_end, title, body_markdown, created_at
            FROM reports
            ORDER BY created_at DESC
            LIMIT %s;
            """,
            (limit,),
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_report(report_id: int) -> dict | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, period_start, period_end, title, body_markdown, created_at
            FROM reports
            WHERE id = %s;
            """,
            (report_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d.name for d in cur.description]
        return dict(zip(cols, row))
