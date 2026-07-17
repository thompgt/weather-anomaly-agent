import type { Anomaly, TimeseriesPoint } from "../types";
import { formatNumber } from "../lib/format";

export function StatTiles({
  data,
  anomalies,
  unit,
}: {
  data: TimeseriesPoint[];
  anomalies: Anomaly[];
  unit: string;
}) {
  const values = data.map((d) => d.avg_value);
  const latest = data[data.length - 1];
  const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : NaN;
  const max = values.length ? Math.max(...values) : NaN;
  const min = values.length ? Math.min(...values) : NaN;

  return (
    <div className="stat-tiles">
      <div className="stat-tile">
        <div className="stat-tile__label">Latest reading</div>
        <div className="stat-tile__value">
          {latest ? `${formatNumber(latest.avg_value)} ${unit}` : "-"}
        </div>
      </div>
      <div className="stat-tile">
        <div className="stat-tile__label">Average (range)</div>
        <div className="stat-tile__value">{Number.isNaN(avg) ? "-" : `${formatNumber(avg)} ${unit}`}</div>
      </div>
      <div className="stat-tile">
        <div className="stat-tile__label">Range min / max</div>
        <div className="stat-tile__value">
          {Number.isNaN(min) ? "-" : `${formatNumber(min)} / ${formatNumber(max)}`}
        </div>
      </div>
      <div className="stat-tile">
        <div className="stat-tile__label">Anomalies in range</div>
        <div className="stat-tile__value">{anomalies.length}</div>
      </div>
    </div>
  );
}
