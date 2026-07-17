import { useState } from "react";
import { StationVariableFilters } from "../components/StationVariableFilters";
import { TimeSeriesChart } from "../components/TimeSeriesChart";
import { StatTiles } from "../components/StatTiles";
import { useTimeseries } from "../hooks/useTimeseries";
import { useAnomalies } from "../hooks/useAnomalies";
import { VARIABLES, type StationId, type Variable } from "../types";
import { startOfDayIso, endOfTodayIso } from "../lib/format";
import { MockBanner } from "../components/MockBanner";

export function DashboardView() {
  const [stationId, setStationId] = useState<StationId>("denver-co");
  const [variable, setVariable] = useState<Variable>("temperature_c");
  const [start, setStart] = useState(startOfDayIso(7));
  const [end, setEnd] = useState(endOfTodayIso());

  const ts = useTimeseries(stationId, variable, start, end);
  const anomaliesQuery = useAnomalies({ station_id: stationId, variable, start, end });

  const variableMeta = VARIABLES.find((v) => v.id === variable)!;
  const anomaliesForVariable = anomaliesQuery.data.filter((a) => a.variable === variable);

  return (
    <div>
      <div className="view-header">
        <h1>Dashboard</h1>
        <p>Hourly readings with statistically-flagged anomalies overlaid.</p>
        {(ts.isMock || anomaliesQuery.isMock) && <MockBanner />}
      </div>

      <StationVariableFilters
        stationId={stationId}
        variable={variable}
        start={start}
        end={end}
        onChange={(next) => {
          setStationId(next.stationId);
          setVariable(next.variable);
          setStart(next.start);
          setEnd(next.end);
        }}
      />

      <StatTiles data={ts.data} anomalies={anomaliesForVariable} unit={variableMeta.unit} />

      <div className="card">
        <div className="card__title">
          {variableMeta.label} ({variableMeta.unit})
        </div>
        {ts.loading ? (
          <div className="loading-note">Loading time series...</div>
        ) : ts.error ? (
          <div className="error-banner">{ts.error}</div>
        ) : (
          <TimeSeriesChart
            data={ts.data}
            anomalies={anomaliesForVariable}
            unit={variableMeta.unit}
            variableLabel={variableMeta.label}
          />
        )}
      </div>
    </div>
  );
}
