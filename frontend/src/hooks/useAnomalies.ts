import { useEffect, useState } from "react";
import { fetchAnomalies, type AnomaliesQuery } from "../api/client";
import type { Anomaly } from "../types";

export interface UseAnomaliesResult {
  data: Anomaly[];
  loading: boolean;
  error: string | null;
  isMock: boolean;
  refetch: () => void;
}

export function useAnomalies(query: AnomaliesQuery): UseAnomaliesResult {
  const [data, setData] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isMock, setIsMock] = useState(false);
  const [tick, setTick] = useState(0);

  const key = JSON.stringify(query);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchAnomalies(query)
      .then((res) => {
        if (cancelled) return;
        setData(res.data);
        setIsMock(res.isMock);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load anomalies");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick]);

  return { data, loading, error, isMock, refetch: () => setTick((t) => t + 1) };
}
