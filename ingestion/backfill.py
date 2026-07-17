"""Backfill historical weather data (Open-Meteo archive API) for the
configured stations, needed to build climatology baselines for anomaly
detection. Reuses fetch_hourly/upsert_readings — same normalization and
upsert path as fetch.py, just a different Open-Meteo endpoint and date range.

Run (from repo root, with .env populated):
    python -m ingestion.backfill
    python -m ingestion.backfill --start 2020-01-01 --end 2025-12-31
"""
from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta

from dotenv import load_dotenv

from .config import BACKFILL_START_DATE, STATIONS
from .db import upsert_readings
from .openmeteo import fetch_hourly

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _default_end_date() -> str:
    # Archive API lags behind real-time; yesterday is safely available.
    return (date.today() - timedelta(days=1)).isoformat()


def run_backfill(start_date: str, end_date: str) -> int:
    total = 0
    for station in STATIONS:
        rows = fetch_hourly(
            ARCHIVE_URL,
            station,
            {"start_date": start_date, "end_date": end_date},
        )
        if not rows:
            logger.warning("Station %s: no rows fetched for %s..%s", station["id"], start_date, end_date)
            continue
        written = upsert_readings(rows)
        total += written
        logger.info("Station %s: upserted %d rows", station["id"], written)
    logger.info("Backfill complete: %d rows upserted across %d stations", total, len(STATIONS))
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill historical readings from Open-Meteo archive API")
    parser.add_argument("--start", default=BACKFILL_START_DATE, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=_default_end_date(), help="End date YYYY-MM-DD")
    args = parser.parse_args()
    run_backfill(args.start, args.end)


if __name__ == "__main__":
    load_dotenv()
    main()
