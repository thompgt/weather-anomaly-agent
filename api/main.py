"""
FastAPI app for the weather anomaly project.

Exposes read endpoints over the shared TimescaleDB schema (readings_hourly,
anomalies, reports) plus a /chat endpoint that reuses the same Claude agent
tools defined in agent/tools.py (no reimplementation of agent logic), and a
WebSocket endpoint that polls `anomalies` for newly-inserted rows and streams
them to connected clients.

Run locally from the repo root:
    uvicorn api.main:app --reload

DATABASE_URL / ANTHROPIC_API_KEY are read from the environment (python-dotenv
picks up a repo-root .env), same convention as ingestion/detection/agent.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

import anthropic
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .models import (
    Anomaly,
    AnomaliesResponse,
    ChatRequest,
    ChatResponse,
    Report,
    ReportsResponse,
    TimeseriesPoint,
    TimeseriesResponse,
)

from agent.tools import ALL_TOOLS

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Polling interval (seconds) for the /anomalies/live WebSocket feed. New
# anomalies are inserted by the detection engine's batch runs, not
# continuously, so a few-second poll is plenty responsive without hammering
# the DB. Configurable via env for tuning.
LIVE_FEED_POLL_INTERVAL_SECONDS = float(os.environ.get("LIVE_FEED_POLL_INTERVAL_SECONDS", "3"))

CHAT_MODEL = os.environ.get("CHAT_MODEL", "claude-opus-4-8")

CHAT_SYSTEM_PROMPT = """You are a Q&A assistant for a weather time series anomaly \
detection system. Users will ask ad hoc questions about weather data, detected \
anomalies, and past reports.

You have tools to query the underlying database: time series readings, anomaly \
records (with filters), raw statistical summaries, and climatology comparisons. \
You can also update an anomaly's status/note or save a report if explicitly asked.

Ground every factual claim in a tool call -- do not invent numbers, station IDs, \
or anomaly details. If a question can't be answered with the available tools \
(e.g. no matching station/variable/time range), say so plainly rather than \
guessing. Be concise and cite the concrete values you observed."""

anthropic_client = anthropic.Anthropic()

# Optional shared-secret auth. Unset (the default for local dev/docker-compose)
# means every route below is open -- set API_KEY before exposing this service
# beyond localhost. Enforced via a dependency rather than middleware so the
# WebSocket route (which authenticates itself separately, see below) and the
# health check at "/" can opt out explicitly.
API_KEY = os.environ.get("API_KEY")


def require_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")


app = FastAPI(
    title="Weather Anomaly API",
    description="Read API + chat endpoint over the weather anomaly detection pipeline.",
)

# Permissive CORS for local dev -- the frontend runs on a different port
# (Vite default 5173). Tighten this before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    response = await call_next(request)
    logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
    return response


@app.get("/")
def root() -> dict:
    return {"service": "weather-anomaly-api", "status": "ok"}


@app.get("/timeseries", response_model=TimeseriesResponse, dependencies=[Depends(require_api_key)])
def get_timeseries(
    station_id: str = Query(..., description="Station identifier, e.g. 'denver-co'."),
    variable: str = Query(..., description="Weather variable, e.g. 'temperature_c'."),
    start: datetime = Query(..., description="ISO 8601 start timestamp."),
    end: datetime = Query(..., description="ISO 8601 end timestamp."),
) -> TimeseriesResponse:
    if start > end:
        raise HTTPException(status_code=400, detail="start must be <= end")

    source, rows = db.fetch_timeseries(station_id, variable, start, end)
    return TimeseriesResponse(
        station_id=station_id,
        variable=variable,
        source=source,
        points=[TimeseriesPoint(**row) for row in rows],
    )


@app.get("/anomalies", response_model=AnomaliesResponse, dependencies=[Depends(require_api_key)])
def get_anomalies(
    status: Optional[str] = Query(None, description="new | investigating | confirmed | dismissed"),
    severity: Optional[str] = Query(None, description="low | medium | high"),
    station_id: Optional[str] = Query(None),
    start: Optional[datetime] = Query(None, description="ISO 8601 start timestamp."),
    end: Optional[datetime] = Query(None, description="ISO 8601 end timestamp."),
) -> AnomaliesResponse:
    rows = db.fetch_anomalies(
        status=status, severity=severity, station_id=station_id, start=start, end=end
    )
    anomalies = [Anomaly(**row) for row in rows]
    return AnomaliesResponse(count=len(anomalies), anomalies=anomalies)


@app.get("/reports", response_model=ReportsResponse, dependencies=[Depends(require_api_key)])
def get_reports() -> ReportsResponse:
    rows = db.fetch_reports()
    reports = [Report(**row) for row in rows]
    return ReportsResponse(count=len(reports), reports=reports)


@app.get("/reports/{report_id}", response_model=Report, dependencies=[Depends(require_api_key)])
def get_report(report_id: int) -> Report:
    row = db.fetch_report(report_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return Report(**row)


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
def chat(request: ChatRequest) -> ChatResponse:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")

    runner = anthropic_client.beta.messages.tool_runner(
        model=CHAT_MODEL,
        max_tokens=4096,
        system=CHAT_SYSTEM_PROMPT,
        tools=ALL_TOOLS,
        messages=[{"role": "user", "content": request.message}],
    )

    final_text_parts: list[str] = []
    for message in runner:
        for block in message.content:
            if block.type == "text" and block.text.strip():
                final_text_parts.append(block.text.strip())

    if not final_text_parts:
        raise HTTPException(status_code=502, detail="Agent returned no text response")

    return ChatResponse(response=final_text_parts[-1])


@app.websocket("/anomalies/live")
async def anomalies_live(websocket: WebSocket) -> None:
    """
    Streams newly-inserted `anomalies` rows to the connected client.

    Simplest-correct approach per the spec: poll the table for rows with
    id > last-seen-id every LIVE_FEED_POLL_INTERVAL_SECONDS and push any new
    ones out as JSON. No LISTEN/NOTIFY -- not worth the added complexity for
    a batch-inserted table.
    """
    if API_KEY and websocket.headers.get("x-api-key") != API_KEY:
        # WebSocket handshakes can't carry a custom header from a browser
        # EventSource-style client uniformly, so also accept it as a query
        # param (?api_key=...) for clients that can't set headers on connect.
        if API_KEY != websocket.query_params.get("api_key"):
            await websocket.close(code=1008)
            return
    await websocket.accept()
    try:
        last_id = await asyncio.to_thread(db.max_anomaly_id)
    except Exception:
        logger.exception("Failed to establish starting anomaly id for live feed")
        await websocket.close(code=1011)
        return

    try:
        while True:
            try:
                new_rows = await asyncio.to_thread(db.fetch_anomalies_since, last_id)
            except Exception:
                logger.exception("Error polling anomalies for live feed")
                await asyncio.sleep(LIVE_FEED_POLL_INTERVAL_SECONDS)
                continue

            for row in new_rows:
                anomaly = Anomaly(**row)
                await websocket.send_json(anomaly.model_dump(mode="json"))
                last_id = max(last_id, anomaly.id)

            await asyncio.sleep(LIVE_FEED_POLL_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        logger.info("Client disconnected from /anomalies/live")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
