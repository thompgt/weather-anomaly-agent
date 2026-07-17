# api

FastAPI service exposing the weather anomaly pipeline's data (readings,
anomalies, reports) as a read API, plus a `/chat` endpoint that reuses the
existing Claude agent tools (`agent/tools.py`) for ad hoc Q&A, and a
WebSocket feed of newly-detected anomalies.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/timeseries` | Hourly-aggregated readings for a station+variable in a time range. Reads `readings_hourly`; falls back to aggregating raw `readings` in SQL if the continuous aggregate is empty. |
| `GET` | `/anomalies` | Detected anomalies, filterable by `status`, `severity`, `station_id`, `start`, `end`. |
| `GET` | `/reports` | All saved reports (newest first). |
| `GET` | `/reports/{id}` | A single report by id. |
| `POST` | `/chat` | Runs the Claude agent (same tools as `agent/monitor.py`, Q&A system prompt) against a free-text question. |
| `WS` | `/anomalies/live` | Streams newly-inserted `anomalies` rows as JSON, polling every few seconds. |

### `GET /timeseries`

```bash
curl "http://localhost:8000/timeseries?station_id=denver-co&variable=temperature_c&start=2026-07-01T00:00:00Z&end=2026-07-08T00:00:00Z"
```

### `GET /anomalies`

```bash
curl "http://localhost:8000/anomalies?status=new&severity=high"
curl "http://localhost:8000/anomalies?station_id=miami-fl&start=2026-07-01T00:00:00Z&end=2026-07-15T00:00:00Z"
```

### `GET /reports` / `GET /reports/{id}`

```bash
curl "http://localhost:8000/reports"
curl "http://localhost:8000/reports/1"
```

### `POST /chat`

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Any high-severity anomalies at seattle-wa in the last week?"}'
```

Response: `{"response": "<final agent text>"}`.

### `WS /anomalies/live`

```bash
# using websocat, wscat, or similar
websocat ws://localhost:8000/anomalies/live
```

Each new `anomalies` row (by ascending `id`, since the connection opened) is
pushed as a JSON object matching the `Anomaly` model used by `/anomalies`.

## Running locally

```bash
cd api
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in DATABASE_URL, ANTHROPIC_API_KEY, etc.
cd ..
uvicorn api.main:app --reload
```

Run from the **repo root** (not from inside `api/`) so that `agent.tools` and
`api.*` both resolve as importable packages -- `uvicorn api.main:app` expects
`api/` to be a package on the Python path, which it is when the working
directory is the repo root.

Requires the Postgres/TimescaleDB instance from `infra/docker-compose.yml`
(or any DB matching `infra/schema.sql`) reachable at `DATABASE_URL`.

## Configuration (env vars)

| Var | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql://weather:weather_dev_password@localhost:5432/weather` | Postgres/TimescaleDB connection string |
| `ANTHROPIC_API_KEY` | - | Required for `/chat` |
| `CHAT_MODEL` | `claude-opus-4-8` | Model used by `/chat`'s tool runner |
| `LIVE_FEED_POLL_INTERVAL_SECONDS` | `3` | How often `/anomalies/live` polls `anomalies` for new rows |

Loaded via `python-dotenv` from a repo-root `.env` (see `.env.example`).

## Docker / docker-compose

`infra/docker-compose.yml` builds this service with `context: ../api` and
injects `DATABASE_URL` pointing at the `db` service; the container listens
on `0.0.0.0:8000` (mapped to host port 8000).

```bash
cd infra
docker compose up -d
```

**Known limitation:** because the compose file's build context is `../api`
only, the Docker image does not include the sibling `agent/` directory that
`/chat` imports (`from agent.tools import ALL_TOOLS`). Every other endpoint
works fine in the container; `/chat` will fail to import at container
startup until either:

- `infra/docker-compose.yml`'s `api` service build context is widened to the
  repo root (e.g. `context: ..`, `dockerfile: api/Dockerfile`) so `agent/`
  can be `COPY`'d in, or
- `agent/` is vendored/copied into `api/` at build time via a script, or
- `/chat`'s tool implementations are inlined into `api/` instead of imported
  from `agent/`.

This wasn't fixed here since `infra/docker-compose.yml` is out of scope for
this change. Running the API directly with `uvicorn` (not Docker) is
unaffected -- `agent/` is a normal sibling package on the Python path there.

## Architecture notes

- Sync `psycopg` (one connection per request), matching the style of
  `agent/db.py` and `detection/db.py` -- no ORM, no connection pool library.
- Pydantic response models (`api/models.py`) for `/timeseries`, `/anomalies`,
  `/reports` -- typed, not raw dicts.
- `/chat` does not reimplement any agent logic: it imports
  `agent.tools.ALL_TOOLS` and calls
  `anthropic.Anthropic().beta.messages.tool_runner(...)`, the same pattern
  `agent/monitor.py` uses for its investigation loop, just with a
  Q&A-oriented system prompt instead of the "investigate and act" one.
- `/anomalies/live` uses polling (`SELECT ... WHERE id > :last_seen`) rather
  than `LISTEN`/`NOTIFY` -- simplest correct approach per the task spec, and
  anomalies are inserted in batches by the detection engine's periodic runs
  rather than continuously, so sub-second latency isn't needed.
- CORS is wide open (`allow_origins=["*"]`) for local dev against the Vite
  frontend on a different port. Tighten before any real deployment.
