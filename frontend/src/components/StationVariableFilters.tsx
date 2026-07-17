import { STATIONS, VARIABLES, type StationId, type Variable } from "../types";
import { toInputDate } from "../lib/format";

interface Props {
  stationId: StationId;
  variable: Variable;
  start: string;
  end: string;
  onChange: (next: { stationId: StationId; variable: Variable; start: string; end: string }) => void;
}

export function StationVariableFilters({ stationId, variable, start, end, onChange }: Props) {
  return (
    <div className="filters-row">
      <div className="filter-field">
        <label htmlFor="station-select">Station</label>
        <select
          id="station-select"
          value={stationId}
          onChange={(e) => onChange({ stationId: e.target.value as StationId, variable, start, end })}
        >
          {STATIONS.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </div>
      <div className="filter-field">
        <label htmlFor="variable-select">Variable</label>
        <select
          id="variable-select"
          value={variable}
          onChange={(e) => onChange({ stationId, variable: e.target.value as Variable, start, end })}
        >
          {VARIABLES.map((v) => (
            <option key={v.id} value={v.id}>
              {v.label}
            </option>
          ))}
        </select>
      </div>
      <div className="filter-field">
        <label htmlFor="start-date">Start</label>
        <input
          id="start-date"
          type="date"
          value={toInputDate(new Date(start))}
          max={toInputDate(new Date(end))}
          onChange={(e) => {
            const d = new Date(e.target.value + "T00:00:00.000Z");
            onChange({ stationId, variable, start: d.toISOString(), end });
          }}
        />
      </div>
      <div className="filter-field">
        <label htmlFor="end-date">End</label>
        <input
          id="end-date"
          type="date"
          value={toInputDate(new Date(end))}
          min={toInputDate(new Date(start))}
          onChange={(e) => {
            const d = new Date(e.target.value + "T23:59:59.999Z");
            onChange({ stationId, variable, start, end: d.toISOString() });
          }}
        />
      </div>
    </div>
  );
}
