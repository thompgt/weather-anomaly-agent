"""Fetch current + recent weather data for configured stations and upsert
into the TimescaleDB `readings` table.

Run (from repo root, with .env populated):
    python -m ingestion.fetch
"""
from __future__ import annotations

import logging

from dotenv import load_dotenv

from .config import FETCH_PAST_DAYS, STATIONS
from .db import upsert_readings
from .openmeteo import fetch_hourly

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run_fetch() -> int:
    """Fetch + upsert recent data for all configured stations. Returns rows written."""
    total = 0
    for station in STATIONS:
        rows = fetch_hourly(
            FORECAST_URL,
            station,
            {"past_days": FETCH_PAST_DAYS, "forecast_days": 1},
        )
        if not rows:
            logger.warning("Station %s: no rows fetched", station["id"])
            continue
        written = upsert_readings(rows)
        total += written
    logger.info("Fetch complete: %d rows upserted across %d stations", total, len(STATIONS))
    return total


if __name__ == "__main__":
    load_dotenv()
    run_fetch()
