import type { Anomaly } from "../types";
import { STATIONS, VARIABLES } from "../types";
import { StatusPill } from "./StatusPill";
import { severityToRole, statusToRole, roleLabel } from "../lib/severity";
import { formatDateTime, formatNumber } from "../lib/format";

function stationLabel(id: string): string {
  return STATIONS.find((s) => s.id === id)?.label ?? id;
}

function variableLabel(id: string): string {
  return VARIABLES.find((v) => v.id === id)?.label ?? id;
}

export function AnomaliesFeed({ anomalies }: { anomalies: Anomaly[] }) {
  if (anomalies.length === 0) {
    return <div className="chart-empty">No anomalies match the current filters.</div>;
  }

  return (
    <div className="feed-list">
      {anomalies.map((a) => (
        <div className="feed-item" key={String(a.id)}>
          <div className="feed-item__top">
            <span className="feed-item__title">
              {stationLabel(a.station_id)} - {variableLabel(a.variable)}
            </span>
            <div style={{ display: "flex", gap: 6 }}>
              <StatusPill role={severityToRole(a.severity)} label={roleLabel(severityToRole(a.severity))} />
              <StatusPill role={statusToRole(a.status)} label={a.status || "unknown"} />
            </div>
          </div>
          <div className="feed-item__meta">
            {formatDateTime(a.time)} · value {formatNumber(a.value)} · score {formatNumber(a.score, 2)} · {a.method}
          </div>
          {a.agent_note && (
            <div className="feed-item__note">
              <span className="feed-item__note-label">Agent note</span>
              {a.agent_note}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
