"""Shared Open-Meteo client: request hourly data for a station, validate the
response schema, and normalize it into readings-table rows.

Used by both fetch.py (forecast API, recent/current data) and backfill.py
(archive API, historical data) — the hourly response shape and the
normalization logic are identical between the two endpoints.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

from .config import REQUEST_TIMEOUT_SECONDS, SOURCE, VARIABLES

logger = logging.getLogger(__name__)

REQUIRED_HOURLY_KEYS = {"time", *VARIABLES.keys()}


def _validate_response(payload: dict[str, Any], station_id: str) -> bool:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        logger.error("Station %s: response missing 'hourly' object: %r", station_id, payload)
        return False
    missing = REQUIRED_HOURLY_KEYS - hourly.keys()
    if missing:
        logger.error("Station %s: response missing hourly fields %s", station_id, missing)
        return False
    n = len(hourly["time"])
    for key in VARIABLES:
        if len(hourly[key]) != n:
            logger.error("Station %s: hourly field %s has mismatched length", station_id, key)
            return False
    return True


def fetch_hourly(base_url: str, station: dict, extra_params: dict) -> list[dict]:
    """Call an Open-Meteo hourly endpoint for one station, return normalized rows.

    Each row is a dict ready for db.upsert_readings:
    {time, station_id, variable, value, source}.
    Returns [] (and logs) on any request/validation failure rather than raising.
    """
    station_id = station["id"]
    query = {
        "latitude": station["lat"],
        "longitude": station["lon"],
        "hourly": ",".join(VARIABLES.keys()),
        "timezone": "UTC",
        "temperature_unit": "celsius",
        "wind_speed_unit": "ms",
        **extra_params,
    }
    try:
        resp = requests.get(base_url, params=query, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error("Station %s: request to %s failed: %s", station_id, base_url, exc)
        return []

    if not _validate_response(payload, station_id):
        return []

    hourly = payload["hourly"]
    rows: list[dict] = []
    for i, ts in enumerate(hourly["time"]):
        try:
            when = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        except ValueError:
            logger.warning("Station %s: skipping unparseable timestamp %r", station_id, ts)
            continue
        for om_key, variable_name in VARIABLES.items():
            value = hourly[om_key][i]
            if value is None:
                continue  # gap in source data (e.g. forecast hours not yet observed)
            rows.append(
                {
                    "time": when,
                    "station_id": station_id,
                    "variable": variable_name,
                    "value": float(value),
                    "source": SOURCE,
                }
            )
    return rows
