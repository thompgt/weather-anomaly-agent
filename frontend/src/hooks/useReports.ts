import { useEffect, useState } from "react";
import { fetchReportDetail, fetchReports } from "../api/client";
import type { ReportDetail, ReportSummary } from "../types";

export function useReports() {
  const [data, setData] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isMock, setIsMock] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchReports()
      .then((res) => {
        if (cancelled) return;
        setData(res.data);
        setIsMock(res.isMock);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load reports");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { data, loading, error, isMock };
}

export function useReportDetail(id: string | null) {
  const [data, setData] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isMock, setIsMock] = useState(false);

  useEffect(() => {
    if (!id) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchReportDetail(id)
      .then((res) => {
        if (cancelled) return;
        setData(res.data);
        setIsMock(res.isMock);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load report");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  return { data, loading, error, isMock };
}
