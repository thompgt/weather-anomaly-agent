// Deterministic mock data used as a dev-time fallback when the live API
// (api/, built in parallel) isn't reachable. Lets the frontend be developed
// and demoed against the contract before the backend exists.
import type { Anomaly, ReportDetail, ReportSummary, TimeseriesPoint } from "../types";

function seededRandom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

const VARIABLE_BASELINE: Record<string, { base: number; amp: number; noise: number }> = {
  temperature_c: { base: 18, amp: 8, noise: 1.2 },
  humidity_pct: { base: 55, amp: 20, noise: 4 },
  wind_speed_ms: { base: 4, amp: 3, noise: 1 },
  pressure_hpa: { base: 1013, amp: 6, noise: 1.5 },
};

export function mockTimeseries(
  stationId: string,
  variable: string,
  start: string,
  end: string
): TimeseriesPoint[] {
  const cfg = VARIABLE_BASELINE[variable] ?? { base: 0, amp: 1, noise: 0.2 };
  const startDate = new Date(start);
  const endDate = new Date(end);
  const rand = seededRandom(hashString(stationId + variable));
  const points: TimeseriesPoint[] = [];
  const hourMs = 60 * 60 * 1000;
  for (let t = startDate.getTime(); t <= endDate.getTime(); t += hourMs) {
    const hourOfDay = new Date(t).getUTCHours();
    const diurnal = Math.sin((hourOfDay / 24) * Math.PI * 2 - Math.PI / 2);
    const avg = cfg.base + diurnal * cfg.amp * 0.5 + (rand() - 0.5) * cfg.noise;
    const spread = cfg.noise * (0.6 + rand() * 0.8);
    points.push({
      time: new Date(t).toISOString(),
      avg_value: round(avg),
      min_value: round(avg - spread),
      max_value: round(avg + spread),
    });
  }
  return points;
}

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h) || 1;
}

function round(n: number): number {
  return Math.round(n * 100) / 100;
}

const SEVERITIES = ["low", "medium", "high", "critical"];
const STATUSES = ["open", "acknowledged", "resolved"];
const STATIONS = ["denver-co", "miami-fl", "seattle-wa"];
const VARS = ["temperature_c", "humidity_pct", "wind_speed_ms", "pressure_hpa"];

export function mockAnomalies(): Anomaly[] {
  const rand = seededRandom(42);
  const now = Date.now();
  const list: Anomaly[] = [];
  for (let i = 0; i < 24; i++) {
    const station = STATIONS[Math.floor(rand() * STATIONS.length)];
    const variable = VARS[Math.floor(rand() * VARS.length)];
    const severity = SEVERITIES[Math.floor(rand() * SEVERITIES.length)];
    const status = STATUSES[Math.floor(rand() * STATUSES.length)];
    const time = new Date(now - i * 3.7 * 60 * 60 * 1000);
    const windowEnd = new Date(time.getTime() + 60 * 60 * 1000);
    list.push({
      id: `mock-${i}`,
      time: time.toISOString(),
      window_end: windowEnd.toISOString(),
      station_id: station,
      variable,
      value: round((rand() - 0.5) * 40 + 20),
      score: round(1 + rand() * 5),
      method: rand() > 0.5 ? "seasonal_hybrid_esd" : "zscore",
      severity,
      status,
      agent_note:
        rand() > 0.4
          ? sampleNote(station, variable, severity)
          : null,
    });
  }
  return list.sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime());
}

function sampleNote(station: string, variable: string, severity: string): string {
  return `Observed a ${severity} deviation in ${variable.replace("_", " ")} at ${station}. Pattern is consistent with a short-lived local front rather than a sensor fault; recommend monitoring the next 3 readings before escalating.`;
}

export function mockReports(): ReportSummary[] {
  const now = Date.now();
  return Array.from({ length: 6 }).map((_, i) => {
    const periodEnd = new Date(now - i * 7 * 24 * 60 * 60 * 1000);
    const periodStart = new Date(periodEnd.getTime() - 7 * 24 * 60 * 60 * 1000);
    return {
      id: `mock-report-${i}`,
      period_start: periodStart.toISOString(),
      period_end: periodEnd.toISOString(),
      title: `Weekly anomaly summary — week of ${periodStart.toISOString().slice(0, 10)}`,
      created_at: periodEnd.toISOString(),
    };
  });
}

export function mockReportDetail(id: string): ReportDetail {
  const summary =
    mockReports().find((r) => String(r.id) === String(id)) ?? mockReports()[0];
  return {
    ...summary,
    body_markdown: `# ${summary.title}\n\nThis report is **mock data** rendered because the live API at \`api/\` was not reachable.\n\n## Highlights\n\n- 3 stations monitored: Denver CO, Miami FL, Seattle WA\n- 4 variables tracked: temperature, humidity, wind speed, pressure\n- Several anomalies flagged by the statistical detector and reviewed by the agent\n\n## Notes\n\n> Once the backend is running, this view will render the real \`body_markdown\` returned by \`GET /reports/{id}\`.\n\n| Station | Anomalies | Notes |\n|---|---|---|\n| denver-co | 3 | Mostly wind speed spikes |\n| miami-fl | 5 | Humidity swings during storm activity |\n| seattle-wa | 2 | Minor pressure drift |\n`,
  };
}

export function mockChatResponse(message: string): string {
  return `(mock agent) I can't reach the live API right now, so this is a canned response. You asked: "${message}". Once \`api/\` is running, POST /chat will return the real agent's answer.`;
}
