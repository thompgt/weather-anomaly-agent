"""
Read-only DB helpers for the agent's tools.

Every tool the agent can call goes through here — plain SQL, no writes except
updating an anomaly's status/agent_note after investigation. Keeps the agent's
output grounded in real data instead of relying on the LLM for numbers.
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


def query_timeseries(station_id: str, variable: str, start: datetime, end: datetime) -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT bucket AS time, avg_value, min_value, max_value
            FROM readings_hourly
            WHERE station_id = %s AND variable = %s AND bucket BETWEEN %s AND %s
            ORDER BY bucket;
            """,
            (station_id, variable, start, end),
        )
        cols = ["time", "avg_value", "min_value", "max_value"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_anomalies(
    start: datetime | None = None,
    end: datetime | None = None,
    severity: str | None = None,
    status: str | None = None,
    station_id: str | None = None,
) -> list[dict]:
    clauses = []
    params: list = []
    if start:
        clauses.append("time >= %s")
        params.append(start)
    if end:
        clauses.append("time <= %s")
        params.append(end)
    if severity:
        clauses.append("severity = %s")
        params.append(severity)
    if status:
        clauses.append("status = %s")
        params.append(status)
    if station_id:
        clauses.append("station_id = %s")
        params.append(station_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, time, window_end, station_id, variable, value, score,
                   method, severity, status, agent_note
            FROM anomalies
            {where}
            ORDER BY time DESC
            LIMIT 200;
            """,
            params,
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def run_stat_summary(station_id: str, variable: str, start: datetime, end: datetime) -> dict:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT avg(value), min(value), max(value), stddev(value), count(*)
            FROM readings
            WHERE station_id = %s AND variable = %s AND time BETWEEN %s AND %s;
            """,
            (station_id, variable, start, end),
        )
        avg, min_v, max_v, stddev, count = cur.fetchone()
        return {
            "avg": avg, "min": min_v, "max": max_v, "stddev": stddev, "count": count,
        }


def compare_to_climatology(station_id: str, variable: str, start: datetime, end: datetime) -> dict:
    """Compare the [start, end] window's average to the same day-of-year window across all history."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT avg(value) FROM readings
            WHERE station_id = %s AND variable = %s AND time BETWEEN %s AND %s;
            """,
            (station_id, variable, start, end),
        )
        (window_avg,) = cur.fetchone()

        cur.execute(
            """
            SELECT avg(value) FROM readings
            WHERE station_id = %s AND variable = %s
              AND extract(doy from time) BETWEEN extract(doy from %s::timestamptz) - 7
                                              AND extract(doy from %s::timestamptz) + 7;
            """,
            (station_id, variable, start, end),
        )
        (climatology_avg,) = cur.fetchone()

        return {
            "window_avg": window_avg,
            "climatology_avg": climatology_avg,
            "delta": (window_avg - climatology_avg) if (window_avg is not None and climatology_avg is not None) else None,
        }


def update_anomaly(anomaly_id: int, status: str | None = None, agent_note: str | None = None) -> None:
    sets, params = [], []
    if status:
        sets.append("status = %s")
        params.append(status)
    if agent_note:
        sets.append("agent_note = %s")
        params.append(agent_note)
    if not sets:
        return
    params.append(anomaly_id)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE anomalies SET {', '.join(sets)} WHERE id = %s;", params)
        conn.commit()


def insert_report(period_start: datetime, period_end: datetime, title: str, body_markdown: str) -> int:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO reports (period_start, period_end, title, body_markdown)
            VALUES (%s, %s, %s, %s) RETURNING id;
            """,
            (period_start, period_end, title, body_markdown),
        )
        (report_id,) = cur.fetchone()
        conn.commit()
        return report_id
