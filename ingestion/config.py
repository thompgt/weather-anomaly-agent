"""Ingestion configuration: stations, variables, and env-driven settings.

Kept as plain constants (no config framework) — override via environment
variables where noted, or edit STATIONS directly for a permanent change.
"""
from __future__ import annotations

import json
import os

# Example stations (lat/lon). Override by setting STATIONS_JSON to a JSON
# array of {"id", "name", "lat", "lon"} objects.
_DEFAULT_STATIONS = [
    {"id": "denver-co", "name": "Denver, CO", "lat": 39.7392, "lon": -104.9903},
    {"id": "miami-fl", "name": "Miami, FL", "lat": 25.7617, "lon": -80.1918},
    {"id": "seattle-wa", "name": "Seattle, WA", "lat": 47.6062, "lon": -122.3321},
]

_stations_json = os.environ.get("STATIONS_JSON")
STATIONS: list[dict] = json.loads(_stations_json) if _stations_json else _DEFAULT_STATIONS

# Open-Meteo hourly parameter name -> readings.variable name.
# Units are normalized at request time (see openmeteo.py: temperature_unit=celsius,
# wind_speed_unit=ms; humidity is already % and surface_pressure already hPa).
VARIABLES: dict[str, str] = {
    "temperature_2m": "temperature_c",
    "relative_humidity_2m": "humidity_pct",
    "wind_speed_10m": "wind_speed_ms",
    "surface_pressure": "pressure_hpa",
}

SOURCE = "open-meteo"

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://weather:weather_dev_password@localhost:5432/weather"
)

# fetch.py / scheduler.py
FETCH_INTERVAL_MINUTES = int(os.environ.get("FETCH_INTERVAL_MINUTES", "30"))
FETCH_PAST_DAYS = int(os.environ.get("FETCH_PAST_DAYS", "2"))

# backfill.py
BACKFILL_START_DATE = os.environ.get("BACKFILL_START_DATE", "2015-01-01")

REQUEST_TIMEOUT_SECONDS = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30"))
DB_RETRIES = int(os.environ.get("DB_RETRIES", "3"))
DB_RETRY_DELAY_SECONDS = float(os.environ.get("DB_RETRY_DELAY_SECONDS", "5"))
