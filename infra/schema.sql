-- TimescaleDB schema: shared contract for ingestion, detection, api, agent.
-- Apply with: psql -f infra/schema.sql

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Raw sensor/API readings, one row per (time, station, variable).
CREATE TABLE IF NOT EXISTS readings (
    time        TIMESTAMPTZ NOT NULL,
    station_id  TEXT NOT NULL,
    variable    TEXT NOT NULL,      -- e.g. 'temperature_c', 'humidity_pct', 'wind_speed_ms', 'pressure_hpa'
    value       DOUBLE PRECISION NOT NULL,
    source      TEXT NOT NULL DEFAULT 'open-meteo',
    PRIMARY KEY (time, station_id, variable)
);

SELECT create_hypertable('readings', by_range('time'), if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_readings_station_var_time
    ON readings (station_id, variable, time DESC);

-- Hourly continuous aggregate.
CREATE MATERIALIZED VIEW IF NOT EXISTS readings_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    station_id,
    variable,
    avg(value)   AS avg_value,
    min(value)   AS min_value,
    max(value)   AS max_value,
    count(*)     AS sample_count
FROM readings
GROUP BY bucket, station_id, variable
WITH NO DATA;

SELECT add_continuous_aggregate_policy('readings_hourly',
    start_offset => INTERVAL '3 days',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

-- Daily continuous aggregate, built on top of the hourly one.
CREATE MATERIALIZED VIEW IF NOT EXISTS readings_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', bucket) AS day,
    station_id,
    variable,
    avg(avg_value) AS avg_value,
    min(min_value) AS min_value,
    max(max_value) AS max_value
FROM readings_hourly
GROUP BY day, station_id, variable
WITH NO DATA;

SELECT add_continuous_aggregate_policy('readings_daily',
    start_offset => INTERVAL '30 days',
    end_offset   => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Detected anomalies, written by the detection engine, read by the agent + API.
CREATE TABLE IF NOT EXISTS anomalies (
    id          BIGSERIAL PRIMARY KEY,
    time        TIMESTAMPTZ NOT NULL,      -- timestamp of the anomalous reading/window start
    window_end  TIMESTAMPTZ,               -- null for point anomalies
    station_id  TEXT NOT NULL,
    variable    TEXT NOT NULL,
    value       DOUBLE PRECISION,
    score       DOUBLE PRECISION NOT NULL, -- method-specific anomaly score
    method      TEXT NOT NULL,             -- e.g. 'stl_zscore', 's_h_esd', 'isolation_forest'
    severity    TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high')),
    status      TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'investigating', 'confirmed', 'dismissed')),
    agent_note  TEXT,                      -- filled in by the AI agent after investigation
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_anomalies_status_time ON anomalies (status, time DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_station_var ON anomalies (station_id, variable, time DESC);

-- Agent-generated reports (scheduled summaries).
CREATE TABLE IF NOT EXISTS reports (
    id          BIGSERIAL PRIMARY KEY,
    period_start TIMESTAMPTZ NOT NULL,
    period_end   TIMESTAMPTZ NOT NULL,
    title        TEXT NOT NULL,
    body_markdown TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
