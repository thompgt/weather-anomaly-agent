// Thin fetch client against the api/ contract. Every getter falls back to
// deterministic mock data (see mockData.ts) when the network call fails,
// so the frontend is fully usable during dev before/without api/ running.
import type { Anomaly, ReportDetail, ReportSummary, TimeseriesPoint } from "../types";
import {
  mockAnomalies,
  mockChatResponse,
  mockReportDetail,
  mockReports,
  mockTimeseries,
} from "./mockData";

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

async function getJson<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  const url = new URL(API_BASE_URL + path);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") url.searchParams.set(key, value);
    }
  }
  const res = await fetch(url.toString(), {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`${path} responded ${res.status}`);
  return (await res.json()) as T;
}

export interface TimeseriesQuery {
  station_id: string;
  variable: string;
  start: string;
  end: string;
}

export async function fetchTimeseries(query: TimeseriesQuery): Promise<{
  data: TimeseriesPoint[];
  isMock: boolean;
}> {
  try {
    const data = await getJson<TimeseriesPoint[]>("/timeseries", { ...query });
    return { data, isMock: false };
  } catch (err) {
    console.warn("[api] /timeseries unreachable, falling back to mock data", err);
    return {
      data: mockTimeseries(query.station_id, query.variable, query.start, query.end),
      isMock: true,
    };
  }
}

export interface AnomaliesQuery {
  status?: string;
  severity?: string;
  station_id?: string;
  variable?: string;
  start?: string;
  end?: string;
}

export async function fetchAnomalies(
  query: AnomaliesQuery = {}
): Promise<{ data: Anomaly[]; isMock: boolean }> {
  try {
    const data = await getJson<Anomaly[]>("/anomalies", { ...query });
    return { data, isMock: false };
  } catch (err) {
    console.warn("[api] /anomalies unreachable, falling back to mock data", err);
    return { data: mockAnomalies(), isMock: true };
  }
}

export async function fetchReports(): Promise<{ data: ReportSummary[]; isMock: boolean }> {
  try {
    const data = await getJson<ReportSummary[]>("/reports");
    return { data, isMock: false };
  } catch (err) {
    console.warn("[api] /reports unreachable, falling back to mock data", err);
    return { data: mockReports(), isMock: true };
  }
}

export async function fetchReportDetail(
  id: string
): Promise<{ data: ReportDetail; isMock: boolean }> {
  try {
    const data = await getJson<ReportDetail>(`/reports/${encodeURIComponent(id)}`);
    return { data, isMock: false };
  } catch (err) {
    console.warn(`[api] /reports/${id} unreachable, falling back to mock data`, err);
    return { data: mockReportDetail(id), isMock: true };
  }
}

export async function postChat(
  message: string
): Promise<{ response: string; isMock: boolean }> {
  try {
    const res = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    if (!res.ok) throw new Error(`/chat responded ${res.status}`);
    const json = (await res.json()) as { response: string };
    return { response: json.response, isMock: false };
  } catch (err) {
    console.warn("[api] /chat unreachable, falling back to mock response", err);
    return { response: mockChatResponse(message), isMock: true };
  }
}
