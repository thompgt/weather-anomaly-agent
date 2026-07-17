# Agent

AI agent layer: read-only tools over the DB, a monitor-loop that investigates
new anomalies and drafts alerts, and a scheduled-report generator.

## Setup

```bash
pip install -r agent/requirements.txt
# .env at repo root needs ANTHROPIC_API_KEY, DATABASE_URL, SLACK_WEBHOOK_URL (optional)
```

## Run

```bash
python -m agent.monitor          # one pass: investigate all status='new' anomalies
python -m agent.report --period daily    # or --period weekly
```

## Tools (agent/tools.py)

- `query_timeseries` — hourly-aggregated readings for a station+variable+range
- `get_anomalies` — filtered anomaly list
- `run_stat_summary` — avg/min/max/stddev/count over raw readings
- `compare_to_climatology` — window average vs. historical day-of-year baseline
- `update_anomaly` — set status/agent_note (the only DB write the agent makes to `anomalies`)
- `send_alert` — Slack webhook (channel arg reserved for future multi-channel routing)
- `save_report` — write a generated report to the `reports` table

All tools are read-only against `readings`; the agent never touches the
detection logic in `detection/` — it only interprets what's already flagged.
