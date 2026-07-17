"""
Agent tool definitions. Each tool is a thin wrapper around agent/db.py (or
alerting.py) so the agent's answers are grounded in real DB queries and not
invented numbers. Uses the Anthropic SDK's @beta_tool decorator + tool_runner.
"""

from __future__ import annotations

from datetime import datetime

from anthropic import beta_tool

from . import db
from .alerting import send_alert as _send_alert


@beta_tool
def query_timeseries(station_id: str, variable: str, start: str, end: str) -> str:
    """Get hourly-aggregated time series readings for a station+variable in a time range.

    Args:
        station_id: Station identifier, e.g. "denver-co", "miami-fl", "seattle-wa".
        variable: One of "temperature_c", "humidity_pct", "wind_speed_ms", "pressure_hpa".
        start: ISO 8601 start timestamp, e.g. "2026-07-01T00:00:00Z".
        end: ISO 8601 end timestamp.
    """
    rows = db.query_timeseries(station_id, variable, datetime.fromisoformat(start), datetime.fromisoformat(end))
    return str(rows)


@beta_tool
def get_anomalies(
    start: str = "", end: str = "", severity: str = "", status: str = "", station_id: str = ""
) -> str:
    """Get detected anomalies, optionally filtered by time range, severity, status, or station.

    Args:
        start: ISO 8601 start timestamp, or empty to not filter.
        end: ISO 8601 end timestamp, or empty to not filter.
        severity: "low", "medium", or "high", or empty to not filter.
        status: "new", "investigating", "confirmed", or "dismissed", or empty to not filter.
        station_id: Station identifier, or empty to not filter.
    """
    rows = db.get_anomalies(
        start=datetime.fromisoformat(start) if start else None,
        end=datetime.fromisoformat(end) if end else None,
        severity=severity or None,
        status=status or None,
        station_id=station_id or None,
    )
    return str(rows)


@beta_tool
def run_stat_summary(station_id: str, variable: str, start: str, end: str) -> str:
    """Get avg/min/max/stddev/count for a station+variable over a time range, from raw readings.

    Args:
        station_id: Station identifier.
        variable: Weather variable name.
        start: ISO 8601 start timestamp.
        end: ISO 8601 end timestamp.
    """
    return str(db.run_stat_summary(station_id, variable, datetime.fromisoformat(start), datetime.fromisoformat(end)))


@beta_tool
def compare_to_climatology(station_id: str, variable: str, start: str, end: str) -> str:
    """Compare a time window's average value to the historical climatology baseline
    (same day-of-year +/- 7 days, across all backfilled history) for the same station+variable.

    Args:
        station_id: Station identifier.
        variable: Weather variable name.
        start: ISO 8601 start timestamp of the window to check.
        end: ISO 8601 end timestamp of the window to check.
    """
    return str(
        db.compare_to_climatology(station_id, variable, datetime.fromisoformat(start), datetime.fromisoformat(end))
    )


@beta_tool
def update_anomaly(anomaly_id: int, status: str = "", agent_note: str = "") -> str:
    """Update an anomaly's status and/or attach an investigation note.

    Args:
        anomaly_id: The anomaly's numeric id (from get_anomalies).
        status: New status: "investigating", "confirmed", or "dismissed". Empty to leave unchanged.
        agent_note: Investigation note to attach. Empty to leave unchanged.
    """
    db.update_anomaly(anomaly_id, status=status or None, agent_note=agent_note or None)
    return f"Anomaly {anomaly_id} updated."


@beta_tool
def send_alert(channel: str, message: str) -> str:
    """Send an alert message to the configured alert channel (Slack).

    Args:
        channel: Logical channel name (currently ignored; single webhook configured).
        message: The alert text to send.
    """
    return _send_alert(channel, message)


@beta_tool
def save_report(period_start: str, period_end: str, title: str, body_markdown: str) -> str:
    """Save a generated analysis report.

    Args:
        period_start: ISO 8601 start of the reporting period.
        period_end: ISO 8601 end of the reporting period.
        title: Report title.
        body_markdown: Full report body in markdown.
    """
    report_id = db.insert_report(
        datetime.fromisoformat(period_start), datetime.fromisoformat(period_end), title, body_markdown
    )
    return f"Report saved with id {report_id}."


ALL_TOOLS = [
    query_timeseries,
    get_anomalies,
    run_stat_summary,
    compare_to_climatology,
    update_anomaly,
    send_alert,
    save_report,
]
