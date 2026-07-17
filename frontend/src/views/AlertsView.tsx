import { useState } from "react";
import { useAnomalies } from "../hooks/useAnomalies";
import { useLiveAnomalies } from "../hooks/useLiveAnomalies";
import { AnomaliesFeed } from "../components/AnomaliesFeed";
import { MockBanner } from "../components/MockBanner";
import { STATIONS } from "../types";

const SEVERITIES = ["low", "medium", "high", "critical"];
const STATUSES = ["open", "acknowledged", "resolved"];

export function AlertsView() {
  const [severity, setSeverity] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [stationId, setStationId] = useState<string | null>(null);

  const anomaliesQuery = useAnomalies({
    severity: severity ?? undefined,
    status: status ?? undefined,
    station_id: stationId ?? undefined,
  });
  const { liveAnomalies, connectionState } = useLiveAnomalies();

  // Merge live-streamed anomalies in front, de-duping by id, then apply the
  // same client-side filters so the feed stays consistent while streaming.
  const merged = [
    ...liveAnomalies,
    ...anomaliesQuery.data.filter((a) => !liveAnomalies.some((la) => String(la.id) === String(a.id))),
  ];
  const filtered = merged.filter((a) => {
    if (severity && a.severity !== severity) return false;
    if (status && a.status !== status) return false;
    if (stationId && a.station_id !== stationId) return false;
    return true;
  });

  return (
    <div>
      <div className="view-header">
        <h1>Alerts</h1>
        <p>Most recent anomalies first, with the agent's read on each one when available.</p>
        {anomaliesQuery.isMock && <MockBanner />}
      </div>

      <div className="filters-row" style={{ alignItems: "center" }}>
        <div className="filter-field">
          <label>Severity</label>
          <div className="chip-row">
            <button className="chip" aria-pressed={severity === null} onClick={() => setSeverity(null)}>
              All
            </button>
            {SEVERITIES.map((s) => (
              <button key={s} className="chip" aria-pressed={severity === s} onClick={() => setSeverity(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
        <div className="filter-field">
          <label>Status</label>
          <div className="chip-row">
            <button className="chip" aria-pressed={status === null} onClick={() => setStatus(null)}>
              All
            </button>
            {STATUSES.map((s) => (
              <button key={s} className="chip" aria-pressed={status === s} onClick={() => setStatus(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
        <div className="filter-field">
          <label htmlFor="station-filter">Station</label>
          <select
            id="station-filter"
            value={stationId ?? ""}
            onChange={(e) => setStationId(e.target.value || null)}
          >
            <option value="">All stations</option>
            {STATIONS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-field" style={{ marginLeft: "auto" }}>
          <label>Live feed</label>
          <span className={`live-indicator live-indicator--${connectionState}`}>
            <span className="live-indicator__dot" />
            {connectionState === "open" ? "Connected" : connectionState}
          </span>
        </div>
      </div>

      {anomaliesQuery.loading ? (
        <div className="loading-note">Loading anomalies...</div>
      ) : anomaliesQuery.error ? (
        <div className="error-banner">{anomaliesQuery.error}</div>
      ) : (
        <AnomaliesFeed anomalies={filtered} />
      )}
    </div>
  );
}
