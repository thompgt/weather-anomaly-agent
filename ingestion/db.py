"""Database helpers: connect to TimescaleDB and upsert into the readings hypertable.

Failures here are logged and swallowed (not raised) wherever practical, so a
transient DB outage degrades the caller (skip this cycle) rather than
crashing a long-running process like scheduler.py.
"""
from __future__ import annotations

import logging
import time
from typing import Iterable, Optional

import psycopg

from .config import DATABASE_URL, DB_RETRIES, DB_RETRY_DELAY_SECONDS

logger = logging.getLogger(__name__)

UPSERT_SQL = """
    INSERT INTO readings (time, station_id, variable, value, source)
    VALUES (%(time)s, %(station_id)s, %(variable)s, %(value)s, %(source)s)
    ON CONFLICT (time, station_id, variable)
    DO UPDATE SET value = EXCLUDED.value, source = EXCLUDED.source
"""


def get_connection(
    retries: int = DB_RETRIES, retry_delay_seconds: float = DB_RETRY_DELAY_SECONDS
) -> Optional["psycopg.Connection"]:
    """Connect to TimescaleDB, retrying a few times. Returns None instead of raising."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return psycopg.connect(DATABASE_URL, connect_timeout=10)
        except psycopg.OperationalError as exc:
            last_error = exc
            logger.warning("DB connection attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(retry_delay_seconds)
    logger.error("Could not connect to database after %d attempts: %s", retries, last_error)
    return None


def upsert_readings(
    rows: Iterable[dict],
    retries: int = DB_RETRIES,
    retry_delay_seconds: float = DB_RETRY_DELAY_SECONDS,
) -> int:
    """Upsert reading rows: dicts with time, station_id, variable, value, source.

    Returns the number of rows written; returns 0 (and logs) on any failure
    instead of raising, so callers keep running when the DB is unreachable.
    """
    rows = list(rows)
    if not rows:
        return 0

    conn = get_connection(retries=retries, retry_delay_seconds=retry_delay_seconds)
    if conn is None:
        logger.error("Skipping upsert of %d rows: database unreachable", len(rows))
        return 0

    try:
        with conn:
            with conn.cursor() as cur:
                cur.executemany(UPSERT_SQL, rows)
        logger.info("Upserted %d rows", len(rows))
        return len(rows)
    except psycopg.Error as exc:
        logger.error("Upsert failed, rolled back: %s", exc)
        return 0
    finally:
        conn.close()
