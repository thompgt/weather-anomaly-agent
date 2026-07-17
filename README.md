# Weather Anomaly Agent

Time series weather anomaly detection, supplemented by an AI agent that
monitors detected anomalies and generates scheduled analysis reports.

## Architecture

```
Data sources (Open-Meteo/NOAA)
  -> ingestion/        fetch, validate, normalize, upsert
  -> TimescaleDB        readings hypertable + continuous aggregates
  -> detection/         STL/z-score, seasonal-hybrid ESD anomaly detection -> anomalies table
  -> agent/              Claude agent: monitor-loop alerts + scheduled reports (read-only DB tools)
  -> api/                FastAPI: /timeseries, /anomalies, /reports, /chat
  -> frontend/            React/TS dashboard: charts, alerts feed, report viewer, chat
```

Anomaly detection is deterministic/statistical; the agent interprets and
narrates anomalies already flagged by the engine rather than detecting them
itself, so outputs stay grounded and auditable.

## Getting started

```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY etc.
cd infra
docker compose up -d db
psql "$DATABASE_URL" -f schema.sql   # applied automatically on first db boot too
```

See `ingestion/`, `detection/`, `agent/`, `api/`, `frontend/` for
component-specific READMEs as they're built out.
