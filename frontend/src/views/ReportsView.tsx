import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useReportDetail, useReports } from "../hooks/useReports";
import { MockBanner } from "../components/MockBanner";
import { formatDate, formatDateTime } from "../lib/format";

export function ReportsView() {
  const reportsQuery = useReports();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedId && reportsQuery.data.length > 0) {
      setSelectedId(String(reportsQuery.data[0].id));
    }
  }, [selectedId, reportsQuery.data]);

  const detailQuery = useReportDetail(selectedId);

  return (
    <div>
      <div className="view-header">
        <h1>Reports</h1>
        <p>Scheduled agent-generated analysis summaries.</p>
        {(reportsQuery.isMock || detailQuery.isMock) && <MockBanner />}
      </div>

      {reportsQuery.loading ? (
        <div className="loading-note">Loading reports...</div>
      ) : reportsQuery.error ? (
        <div className="error-banner">{reportsQuery.error}</div>
      ) : reportsQuery.data.length === 0 ? (
        <div className="chart-empty">No reports yet.</div>
      ) : (
        <div className="reports-layout">
          <div className="report-list">
            {reportsQuery.data.map((r) => (
              <button
                key={String(r.id)}
                className="report-list-item"
                aria-current={String(r.id) === selectedId}
                onClick={() => setSelectedId(String(r.id))}
              >
                <div className="report-list-item__title">{r.title}</div>
                <div className="report-list-item__meta">
                  {formatDate(r.period_start)} - {formatDate(r.period_end)}
                </div>
              </button>
            ))}
          </div>

          <div className="card">
            {detailQuery.loading ? (
              <div className="loading-note">Loading report...</div>
            ) : detailQuery.error ? (
              <div className="error-banner">{detailQuery.error}</div>
            ) : detailQuery.data ? (
              <>
                <div className="card__title">{detailQuery.data.title}</div>
                <div className="report-list-item__meta" style={{ marginBottom: 12 }}>
                  Generated {formatDateTime(detailQuery.data.created_at)}
                </div>
                <div className="report-body">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{detailQuery.data.body_markdown}</ReactMarkdown>
                </div>
              </>
            ) : (
              <div className="chart-empty">Select a report to view it.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
