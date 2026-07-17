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
```

`schema.sql` is meant to auto-apply via `docker-entrypoint-initdb.d` on first
boot, but on some TimescaleDB image builds the extension-install step
restarts Postgres mid-init and the remaining init scripts don't run. If
`psql "$DATABASE_URL" -c '\dt'` shows no tables after the container is up,
apply it manually once:

```bash
psql "$DATABASE_URL" -f infra/schema.sql
```

Then, from the repo root, each component's own README has full instructions
(`ingestion/`, `detection/`, `agent/`, `api/`, `frontend/`). End-to-end order:

```bash
pip install -r ingestion/requirements.txt -r detection/requirements.txt -r agent/requirements.txt -r api/requirements.txt
python -m ingestion.backfill        # historical data for climatology baselines
python -m ingestion.fetch           # current/recent data
python -m detection.run             # (run from detection/) flag anomalies
python -m agent.monitor             # investigate new anomalies, draft alerts
uvicorn api.main:app --reload       # API on :8000
cd frontend && npm install && npm run dev   # dashboard on :5173
```

This whole path has been run end-to-end against real Open-Meteo data during
development, including the anomaly detection engine, the FastAPI layer, and
the frontend build — everything except the live `/chat` → Claude API call,
which needs a real `ANTHROPIC_API_KEY`.
