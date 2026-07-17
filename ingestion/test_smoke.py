"""Trivial smoke test for Open-Meteo response normalization.

No network, no DB — mocks requests.get with a fixed payload and checks that
fetch_hourly() produces the expected normalized rows. Not a test framework
setup, just a runnable sanity check.

Run (from repo root):
    python -m ingestion.test_smoke
"""
from __future__ import annotations

from unittest.mock import patch

from .openmeteo import fetch_hourly

FAKE_PAYLOAD = {
    "hourly": {
        "time": ["2026-07-16T00:00", "2026-07-16T01:00"],
        "temperature_2m": [21.5, None],  # None simulates a gap in source data
        "relative_humidity_2m": [55, 57],
        "wind_speed_10m": [3.2, 4.1],
        "surface_pressure": [1013.2, 1012.9],
    }
}


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_hourly_normalizes_and_skips_nulls() -> None:
    station = {"id": "test-station", "lat": 0.0, "lon": 0.0}
    with patch("ingestion.openmeteo.requests.get", return_value=_FakeResponse(FAKE_PAYLOAD)):
        rows = fetch_hourly("https://example.invalid", station, {})

    # 2 timestamps x 4 variables, minus 1 null temperature reading = 7 rows.
    assert len(rows) == 7, f"expected 7 rows, got {len(rows)}"
    assert all(r["station_id"] == "test-station" for r in rows)
    assert all(r["source"] == "open-meteo" for r in rows)
    variables = {r["variable"] for r in rows}
    assert variables == {"temperature_c", "humidity_pct", "wind_speed_ms", "pressure_hpa"}
    print("OK: test_fetch_hourly_normalizes_and_skips_nulls")


if __name__ == "__main__":
    test_fetch_hourly_normalizes_and_skips_nulls()
