"""
Shared DB helpers for the detection component.

Reads DATABASE_URL from the environment (loaded via python-dotenv from a
.env file at the repo root, same convention as the other components).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Sequence

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://weather:weather_dev_password@localhost:5432/weather"
)


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def list_station_variables(conn: psycopg.Connection) -> list[tuple[str, str]]:
    """Distinct (station_id, variable) pairs currently present in readings."""
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT station_id, variable FROM readings ORDER BY 1, 2;")
        return [(row[0], row[1]) for row in cur.fetchall()]


def fetch_series(
    conn: psycopg.Connection,
    station_id: str,
    variable: str,
    start: datetime,
    end: datetime,
    source: str = "hourly",
) -> pd.DataFrame:
    """
    Pull a station+variable time series between [start, end].

    source='hourly' reads the readings_hourly continuous aggregate (avg_value)
    which is what the detectors expect (regular 1h cadence). source='raw'
    reads the readings table directly and resamples to hourly in pandas,
    useful as a fallback if the continuous aggregate hasn't materialized yet
    (e.g. fresh ingestion, before the first refresh policy run).
    """
    if source == "hourly":
        query = """
            SELECT bucket AS time, avg_value AS value
            FROM readings_hourly
            WHERE station_id = %s AND variable = %s
              AND bucket >= %s AND bucket <= %s
            ORDER BY bucket;
        """
    else:
        query = """
            SELECT time_bucket('1 hour', time) AS time, avg(value) AS value
            FROM readings
            WHERE station_id = %s AND variable = %s
              AND time >= %s AND time <= %s
            GROUP BY 1
            ORDER BY 1;
        """
    with conn.cursor() as cur:
        cur.execute(query, (station_id, variable, start, end))
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=["time", "value"])
    if df.empty:
        return df
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()
    # Enforce a regular hourly grid; interpolate small gaps so STL gets an
    # evenly-spaced series. Long gaps just carry through as interpolated
    # (flat-ish) stretches, which won't score as anomalies.
    df = df.resample("1h").mean()
    df["value"] = df["value"].interpolate(limit=6)
    return df


@dataclass
class AnomalyRecord:
    time: datetime
    station_id: str
    variable: str
    value: float
    score: float
    method: str
    severity: str
    window_end: datetime | None = None
    status: str = "new"
    agent_note: str | None = None


def insert_anomalies_deduped(
    conn: psycopg.Connection, records: Sequence[AnomalyRecord]
) -> int:
    """
    Insert AnomalyRecords into `anomalies`, skipping any whose
    (time, station_id, variable, method) already exists.

    There's no unique constraint on those columns in the shared schema (it's
    a fixed contract we can't modify), so dedup happens here in Python:
    look up existing keys for the relevant station/variable/method/time
    range, then filter before inserting.
    """
    if not records:
        return 0

    by_group: dict[tuple[str, str, str], list[AnomalyRecord]] = {}
    for r in records:
        by_group.setdefault((r.station_id, r.variable, r.method), []).append(r)

    to_insert: list[AnomalyRecord] = []
    with conn.cursor() as cur:
        for (station_id, variable, method), group in by_group.items():
            times = [r.time for r in group]
            cur.execute(
                """
                SELECT time FROM anomalies
                WHERE station_id = %s AND variable = %s AND method = %s
                  AND time = ANY(%s);
                """,
                (station_id, variable, method, times),
            )
            existing = {row[0] for row in cur.fetchall()}
            for r in group:
                if r.time not in existing:
                    to_insert.append(r)

    if not to_insert:
        return 0

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO anomalies
                (time, window_end, station_id, variable, value, score, method, severity, status, agent_note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            [
                (
                    r.time,
                    r.window_end,
                    r.station_id,
                    r.variable,
                    r.value,
                    r.score,
                    r.method,
                    r.severity,
                    r.status,
                    r.agent_note,
                )
                for r in to_insert
            ],
        )
    conn.commit()
    return len(to_insert)
