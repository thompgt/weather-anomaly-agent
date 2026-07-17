import { useMemo, useRef, useState } from "react";
import type { Anomaly, TimeseriesPoint } from "../types";
import { severityToRole, roleLabel } from "../lib/severity";
import { formatDateTime, formatNumber } from "../lib/format";

const CHART_W = 900;
const CHART_H = 320;
const PAD = { top: 16, right: 20, bottom: 32, left: 52 };

interface Props {
  data: TimeseriesPoint[];
  anomalies: Anomaly[];
  unit: string;
  variableLabel: string;
}

interface HoverState {
  index: number;
  clientXFraction: number;
}

export function TimeSeriesChart({ data, anomalies, unit, variableLabel }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [hover, setHover] = useState<HoverState | null>(null);

  const plot = useMemo(() => {
    if (data.length === 0) return null;

    const times = data.map((d) => new Date(d.time).getTime());
    const minT = Math.min(...times);
    const maxT = Math.max(...times);
    const allValues = data.flatMap((d) => [d.avg_value, d.min_value, d.max_value]);
    let minV = Math.min(...allValues);
    let maxV = Math.max(...allValues);
    if (minV === maxV) {
      minV -= 1;
      maxV += 1;
    }
    const vPad = (maxV - minV) * 0.1;
    minV -= vPad;
    maxV += vPad;

    const innerW = CHART_W - PAD.left - PAD.right;
    const innerH = CHART_H - PAD.top - PAD.bottom;

    const xScale = (t: number) =>
      PAD.left + (maxT === minT ? innerW / 2 : ((t - minT) / (maxT - minT)) * innerW);
    const yScale = (v: number) => PAD.top + innerH - ((v - minV) / (maxV - minV)) * innerH;

    const linePoints = data.map((d) => ({
      x: xScale(new Date(d.time).getTime()),
      y: yScale(d.avg_value),
    }));
    const linePath = linePoints.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");

    const bandPath =
      data
        .map((d, i) => `${i === 0 ? "M" : "L"}${xScale(new Date(d.time).getTime())},${yScale(d.max_value)}`)
        .join(" ") +
      " " +
      data
        .slice()
        .reverse()
        .map((d) => `L${xScale(new Date(d.time).getTime())},${yScale(d.min_value)}`)
        .join(" ") +
      " Z";

    const yTicks = 4;
    const yTickValues = Array.from({ length: yTicks + 1 }, (_, i) => minV + ((maxV - minV) * i) / yTicks);

    const xTickCount = Math.min(6, data.length);
    const xTickValues = Array.from({ length: xTickCount }, (_, i) => {
      const t = minT + ((maxT - minT) * i) / Math.max(1, xTickCount - 1);
      return t;
    });

    const anomalyPoints = anomalies
      .map((a) => {
        const t = new Date(a.time).getTime();
        if (Number.isNaN(t) || t < minT || t > maxT) return null;
        return {
          anomaly: a,
          x: xScale(t),
          y: yScale(a.value),
        };
      })
      .filter((v): v is { anomaly: Anomaly; x: number; y: number } => v !== null);

    return {
      xScale,
      yScale,
      minT,
      maxT,
      minV,
      maxV,
      linePath,
      bandPath,
      yTickValues,
      xTickValues,
      anomalyPoints,
      dataPoints: data.map((d, i) => ({ ...d, x: linePoints[i].x })),
    };
  }, [data, anomalies]);

  function handlePointerMove(e: React.PointerEvent<SVGRectElement>) {
    if (!plot || data.length === 0) return;
    const rect = (e.target as SVGRectElement).getBoundingClientRect();
    const fraction = (e.clientX - rect.left) / rect.width;
    const targetT = plot.minT + fraction * (plot.maxT - plot.minT);
    let closestIndex = 0;
    let closestDist = Infinity;
    data.forEach((d, i) => {
      const dist = Math.abs(new Date(d.time).getTime() - targetT);
      if (dist < closestDist) {
        closestDist = dist;
        closestIndex = i;
      }
    });
    setHover({ index: closestIndex, clientXFraction: fraction });
  }

  if (!plot) {
    return <div className="chart-empty">No data for this selection.</div>;
  }

  const hoveredPoint = hover ? plot.dataPoints[hover.index] : null;
  const hoveredAnomalies = hoveredPoint
    ? plot.anomalyPoints.filter(
        (ap) => Math.abs(new Date(ap.anomaly.time).getTime() - new Date(hoveredPoint.time).getTime()) < 30 * 60 * 1000
      )
    : [];

  return (
    <div className="chart-wrap" ref={containerRef}>
      <svg viewBox={`0 0 ${CHART_W} ${CHART_H}`} width="100%" height={CHART_H} role="img" aria-label={`${variableLabel} time series with anomaly markers`}>
        {/* gridlines */}
        {plot.yTickValues.map((v, i) => {
          const y = plot.yScale(v);
          return (
            <g key={i}>
              <line x1={PAD.left} x2={CHART_W - PAD.right} y1={y} y2={y} stroke="var(--gridline)" strokeWidth={1} />
              <text x={PAD.left - 8} y={y + 4} textAnchor="end" fontSize={11} fill="var(--text-muted)">
                {formatNumber(v)}
              </text>
            </g>
          );
        })}

        {/* x axis */}
        <line
          x1={PAD.left}
          x2={CHART_W - PAD.right}
          y1={CHART_H - PAD.bottom}
          y2={CHART_H - PAD.bottom}
          stroke="var(--baseline)"
          strokeWidth={1}
        />
        {plot.xTickValues.map((t, i) => (
          <text key={i} x={plot.xScale(t)} y={CHART_H - PAD.bottom + 18} textAnchor="middle" fontSize={11} fill="var(--text-muted)">
            {formatDateTime(new Date(t).toISOString())}
          </text>
        ))}

        {/* min/max band */}
        <path d={plot.bandPath} fill="var(--series-1)" opacity={0.1} stroke="none" />

        {/* avg line */}
        <path d={plot.linePath} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

        {/* anomaly markers */}
        {plot.anomalyPoints.map((ap) => {
          const role = severityToRole(ap.anomaly.severity);
          return (
            <circle
              key={String(ap.anomaly.id)}
              cx={ap.x}
              cy={ap.y}
              r={5}
              fill={`var(--status-${role})`}
              stroke="var(--surface-1)"
              strokeWidth={2}
            />
          );
        })}

        {/* crosshair */}
        {hoveredPoint && (
          <line
            x1={hoveredPoint.x}
            x2={hoveredPoint.x}
            y1={PAD.top}
            y2={CHART_H - PAD.bottom}
            stroke="var(--text-muted)"
            strokeWidth={1}
            strokeDasharray="2,3"
          />
        )}

        {/* hit layer */}
        <rect
          x={PAD.left}
          y={PAD.top}
          width={CHART_W - PAD.left - PAD.right}
          height={CHART_H - PAD.top - PAD.bottom}
          fill="transparent"
          onPointerMove={handlePointerMove}
          onPointerLeave={() => setHover(null)}
        />
      </svg>

      {hoveredPoint && hover && (
        <div
          className="chart-tooltip"
          style={{
            left: `min(${hover.clientXFraction * 100}%, calc(100% - 170px))`,
            top: 8,
          }}
        >
          <div className="chart-tooltip__time">{formatDateTime(hoveredPoint.time)}</div>
          <div className="chart-tooltip__row">
            <span className="chart-tooltip__key">
              <span className="chart-tooltip__stroke" style={{ background: "var(--series-1)" }} />
              Avg
            </span>
            <span className="chart-tooltip__value">
              {formatNumber(hoveredPoint.avg_value)} {unit}
            </span>
          </div>
          <div className="chart-tooltip__row">
            <span className="chart-tooltip__key">Min - Max</span>
            <span className="chart-tooltip__value">
              {formatNumber(hoveredPoint.min_value)} - {formatNumber(hoveredPoint.max_value)}
            </span>
          </div>
          {hoveredAnomalies.map((ap) => (
            <div className="chart-tooltip__row" key={String(ap.anomaly.id)}>
              <span className="chart-tooltip__key">
                <span
                  className="chart-tooltip__stroke"
                  style={{ background: `var(--status-${severityToRole(ap.anomaly.severity)})` }}
                />
                {roleLabel(severityToRole(ap.anomaly.severity))} anomaly
              </span>
              <span className="chart-tooltip__value">{formatNumber(ap.anomaly.value)}</span>
            </div>
          ))}
        </div>
      )}

      <div className="legend">
        <span className="legend__item">
          <span className="legend__swatch" style={{ background: "var(--series-1)" }} />
          {variableLabel} (avg)
        </span>
        <span className="legend__item">
          <span className="legend__swatch" style={{ background: "var(--series-1)", opacity: 0.3 }} />
          min-max range
        </span>
        <span className="legend__item">
          <span className="legend__dot" style={{ background: "var(--status-critical)" }} />
          Critical anomaly
        </span>
        <span className="legend__item">
          <span className="legend__dot" style={{ background: "var(--status-serious)" }} />
          Serious
        </span>
        <span className="legend__item">
          <span className="legend__dot" style={{ background: "var(--status-warning)" }} />
          Warning
        </span>
        <span className="legend__item">
          <span className="legend__dot" style={{ background: "var(--status-good)" }} />
          Low
        </span>
      </div>
    </div>
  );
}
