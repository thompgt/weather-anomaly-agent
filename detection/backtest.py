"""
Sanity-check backtest: does the detection pipeline surface a real,
documented extreme-weather event?

Event chosen: the Pacific Northwest "heat dome" of June 2021. Portland, OR
(station used here: PDX-equivalent lat/lon, but we match against whatever
station_id is present in `readings`) hit an all-time record high of 116F
(46.7C) on 2021-06-28, smashing the prior all-time record of 107F set in
1965 -- a textbook multi-sigma anomaly against the local seasonal norm.
Event window used: 2021-06-25 to 2021-06-29 (build-up through peak).
Source: National Weather Service Portland, OR climate records
(https://www.weather.gov/pqr/PortlandClimateRecords), widely reported
June 2021 Pacific Northwest heat wave.

This is a sanity check, not an evaluation: we don't compute precision/
recall, we just confirm at least one point inside the event window gets
flagged by at least one method.

Data source, in priority order:
  1. Real data: if `readings` already has enough history (backfilled by
     ingestion) for a station whose id looks like it's in the Pacific
     Northwest (portland/pdx/seattle/sea in the id), run detection on it
     directly.
  2. SYNTHETIC FALLBACK: if no such data exists yet (likely, since
     ingestion may not have backfilled 2021 history), generate a synthetic
     hourly temperature series with a realistic diurnal + annual cycle and
     inject a heat-dome-shaped spike over the event window, clearly
     labeled as synthetic. This keeps the backtest runnable standalone
     without depending on ingestion's backfill being done.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import db
from seasonal_esd import seasonal_hybrid_esd
from stl_zscore import detect_stl_zscore

EVENT_START = datetime(2021, 6, 25, tzinfo=timezone.utc)
EVENT_END = datetime(2021, 6, 29, tzinfo=timezone.utc)
EVENT_LABEL = "2021 Pacific Northwest heat dome (Portland, OR record 116F on 2021-06-28)"

PNW_HINTS = ("portland", "pdx", "seattle", "sea", "pnw")


def _find_pnw_station(conn) -> str | None:
    for station_id, variable in db.list_station_variables(conn):
        if variable == "temperature_c" and any(h in station_id.lower() for h in PNW_HINTS):
            return station_id
    return None


def _load_real_data(conn, station_id: str) -> pd.DataFrame:
    history_start = EVENT_START - timedelta(days=30)
    history_end = EVENT_END + timedelta(days=2)
    df = db.fetch_series(conn, station_id, "temperature_c", history_start, history_end)
    return df


def generate_synthetic_heatwave_series() -> pd.DataFrame:
    """
    SYNTHETIC FALLBACK DATA -- not real observations.

    Builds an hourly temperature series covering a 30-day lead-in plus the
    event window, with:
      - a mild seasonal warm-up trend (late-June in the PNW),
      - a diurnal cycle (~10C daily swing, peaking mid-afternoon),
      - Gaussian noise,
      - an injected heat-dome spike over EVENT_START..EVENT_END that
        pushes daytime highs from a normal ~28C up to a synthetic ~46C
        peak, echoing the real event's jump from typical ~28C late-June
        highs to the actual 46.7C record.
    """
    history_start = EVENT_START - timedelta(days=30)
    history_end = EVENT_END + timedelta(days=2)
    idx = pd.date_range(history_start, history_end, freq="1h", tz="UTC")

    rng = np.random.default_rng(seed=42)
    hours = np.asarray((idx - idx[0]).total_seconds() / 3600.0)

    baseline = 18.0  # avg late-June PNW temp, C
    seasonal_ramp = 0.02 * hours / 24  # slight warm-up trend over the month
    diurnal = 6.0 * np.sin(2 * np.pi * (hours % 24) / 24 - np.pi / 2)  # peak mid-afternoon
    noise = rng.normal(0, 0.8, size=len(idx))

    values = baseline + seasonal_ramp + diurnal + noise

    in_event = (idx >= pd.Timestamp(EVENT_START)) & (idx <= pd.Timestamp(EVENT_END))
    event_hours = (idx[in_event] - pd.Timestamp(EVENT_START)).total_seconds() / 3600.0
    total_event_hours = (pd.Timestamp(EVENT_END) - pd.Timestamp(EVENT_START)).total_seconds() / 3600.0
    # Ramp up to peak mid-event, echoing the real event's building heat dome.
    ramp_shape = np.sin(np.pi * event_hours / total_event_hours) ** 1.5
    spike = 20.0 * ramp_shape  # up to +20C over baseline at peak
    values[in_event] += spike

    df = pd.DataFrame({"value": values}, index=idx)
    df.index.name = "time"
    return df


def run_backtest(source: str = "auto") -> None:
    used_real_data = False
    df = pd.DataFrame()

    if source in ("auto", "real"):
        conn = db.get_connection()
        try:
            station_id = _find_pnw_station(conn)
            if station_id:
                df = _load_real_data(conn, station_id)
                if len(df.dropna()) >= 30 * 24 * 0.5:  # at least ~half the history window populated
                    used_real_data = True
                    print(f"Using REAL data from readings for station_id={station_id!r}.")
                else:
                    print(f"Found station {station_id!r} but not enough history yet; falling back.")
        finally:
            conn.close()

    if not used_real_data:
        if source == "real":
            raise SystemExit("No sufficient real data found in readings and --source=real was forced.")
        print(
            "\n*** No sufficient real backfilled data found for a Pacific NW station. ***\n"
            "*** Falling back to SYNTHETIC data with an injected heat-dome spike.    ***\n"
            "*** This validates the pipeline mechanics only, not real-world recall.  ***\n"
        )
        df = generate_synthetic_heatwave_series()

    print(f"\nEvent under test: {EVENT_LABEL}")
    print(f"Event window: {EVENT_START.date()} to {EVENT_END.date()}\n")

    stl_flagged = detect_stl_zscore(df)
    esd_flagged = seasonal_hybrid_esd(df)

    def in_event(index) -> pd.DatetimeIndex:
        return index[(index >= pd.Timestamp(EVENT_START)) & (index <= pd.Timestamp(EVENT_END))]

    stl_hits = in_event(stl_flagged.index)
    esd_hits = in_event(esd_flagged.index)

    print(f"stl_zscore: {len(stl_flagged)} points flagged total, {len(stl_hits)} inside the event window.")
    if len(stl_hits):
        peak = stl_flagged.loc[stl_hits, "score"].abs().idxmax()
        row = stl_flagged.loc[peak]
        print(f"  peak hit: {peak}  value={row.value:.1f}C  score={row.score:.2f}")

    print(f"s_h_esd:    {len(esd_flagged)} points flagged total, {len(esd_hits)} inside the event window.")
    if len(esd_hits):
        peak = esd_flagged.loc[esd_hits, "score"].abs().idxmax()
        row = esd_flagged.loc[peak]
        print(f"  peak hit: {peak}  value={row.value:.1f}C  score={row.score:.2f}")

    surfaced = len(stl_hits) > 0 or len(esd_hits) > 0
    print()
    if surfaced:
        print("PASS: the pipeline surfaced the event (flagged >=1 point inside the event window).")
    else:
        print("FAIL: neither method flagged a point inside the event window.")
    raise SystemExit(0 if surfaced else 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=["auto", "real", "synthetic"],
        default="auto",
        help="auto (default): use real data if available, else synthetic fallback. "
        "real: require real data, error out if unavailable. "
        "synthetic: always use the synthetic fallback.",
    )
    args = parser.parse_args()
    run_backtest(source=args.source)


if __name__ == "__main__":
    main()
