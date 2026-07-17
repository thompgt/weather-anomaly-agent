// Types mirroring the API contract in the project README / build brief.
// Kept intentionally loose on enum-like string fields (severity, status,
// method) since the backend's exact vocabulary isn't pinned down yet -
// the UI maps known keywords defensively and falls back gracefully.

export type StationId = "denver-co" | "miami-fl" | "seattle-wa";

export const STATIONS: { id: StationId; label: string }[] = [
  { id: "denver-co", label: "Denver, CO" },
  { id: "miami-fl", label: "Miami, FL" },
  { id: "seattle-wa", label: "Seattle, WA" },
];

export type Variable =
  | "temperature_c"
  | "humidity_pct"
  | "wind_speed_ms"
  | "pressure_hpa";

export const VARIABLES: { id: Variable; label: string; unit: string }[] = [
  { id: "temperature_c", label: "Temperature", unit: "°C" },
  { id: "humidity_pct", label: "Humidity", unit: "%" },
  { id: "wind_speed_ms", label: "Wind speed", unit: "m/s" },
  { id: "pressure_hpa", label: "Pressure", unit: "hPa" },
];

export interface TimeseriesPoint {
  time: string;
  avg_value: number;
  min_value: number;
  max_value: number;
}

export interface Anomaly {
  id: string | number;
  time: string;
  window_end: string;
  station_id: string;
  variable: string;
  value: number;
  score: number;
  method: string;
  severity: string;
  status: string;
  agent_note?: string | null;
}

export interface ReportSummary {
  id: string | number;
  period_start: string;
  period_end: string;
  title: string;
  created_at: string;
}

export interface ReportDetail extends ReportSummary {
  body_markdown: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "agent";
  text: string;
  pending?: boolean;
  error?: boolean;
}
