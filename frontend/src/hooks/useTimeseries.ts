import { useEffect, useState } from "react";
import { fetchTimeseries } from "../api/client";
import type { TimeseriesPoint } from "../types";

export interface UseTimeseriesResult {
  data: TimeseriesPoint[];
  loading: boolean;
  error: string | null;
  isMock: boolean;
}

export function useTimeseries(
  stationId: string,
  variable: string,
  start: string,
  end: string
): UseTimeseriesResult {
  const [data, setData] = useState<TimeseriesPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isMock, setIsMock] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchTimeseries({ station_id: stationId, variable, start, end })
      .then((res) => {
        if (cancelled) return;
        setData(res.data);
        setIsMock(res.isMock);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load timeseries");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [stationId, variable, start, end]);

  return { data, loading, error, isMock };
}
