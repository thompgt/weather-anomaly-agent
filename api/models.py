"""Pydantic response models for the API. Typed shapes over the raw DB rows so
FastAPI can validate/serialize consistently and generate an accurate OpenAPI
schema, instead of returning ad hoc dicts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TimeseriesPoint(BaseModel):
    time: datetime
    avg_value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    sample_count: Optional[int] = None


class TimeseriesResponse(BaseModel):
    station_id: str
    variable: str
    source: str  # "readings_hourly" or "readings" (fallback aggregation)
    points: list[TimeseriesPoint]


class Anomaly(BaseModel):
    id: int
    time: datetime
    window_end: Optional[datetime] = None
    station_id: str
    variable: str
    value: Optional[float] = None
    score: float
    method: str
    severity: str
    status: str
    agent_note: Optional[str] = None
    created_at: Optional[datetime] = None


class AnomaliesResponse(BaseModel):
    count: int
    anomalies: list[Anomaly]


class Report(BaseModel):
    id: int
    period_start: datetime
    period_end: datetime
    title: str
    body_markdown: str
    created_at: datetime


class ReportsResponse(BaseModel):
    count: int
    reports: list[Report]


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
