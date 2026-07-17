# Weather Anomaly Agent — frontend

React + TypeScript + Vite dashboard for the weather anomaly detection
project: time series charts with anomaly overlays, an alerts/anomalies feed
(with live streaming), a report viewer, and a chat panel backed by the
`api/` FastAPI service.

## Run the dev server

```bash
npm install
npm run dev
```

Vite serves on `http://localhost:5173` by default.

## Environment configuration

Set the API base URL via `VITE_API_BASE_URL` (a `.env` file at
`frontend/.env`, or an exported env var before `npm run dev`):

```
VITE_API_BASE_URL=http://localhost:8000
```

If unset, it defaults to `http://localhost:8000`. The WebSocket endpoint for
live anomalies (`/anomalies/live`) is derived from this same base URL
(`http`→`ws`, `https`→`wss`).

**If the API isn't reachable** (e.g. `api/` hasn't been built/started yet),
every view falls back to deterministic mock data automatically and shows a
"Showing mock data" banner, so the frontend is fully explorable on its own.

## Build

```bash
npm run build   # tsc -b && vite build
npm run preview # serve the production build locally
```

## Docker

`infra/docker-compose.yml` builds this directory and passes
`VITE_API_BASE_URL` in; the container runs the Vite dev server on port 5173
(`docker compose up frontend` from `infra/`).

## Structure

```
src/
  api/          fetch client (client.ts) + dev-time mock data (mockData.ts)
  components/   chart, feed, filters, stat tiles, status pill, markdown-rendered report body
  hooks/        useTimeseries, useAnomalies, useLiveAnomalies (WS), useReports, useChat
  views/        DashboardView, AlertsView, ReportsView, ChatView (one per nav tab)
  lib/          formatting + severity/status -> color-role mapping
  styles/       design tokens (theme.css) + layout/component CSS (app.css)
```

## Library choices

- **Data fetching:** plain `fetch` + hooks (`useEffect`/`useState`), no React
  Query. Four views with independent, not-heavily-shared queries didn't
  justify the dependency; each hook already handles loading/error/mock-fallback
  state directly.
- **Markdown rendering:** `react-markdown` + `remark-gfm` for the report
  viewer, so report tables/checklists render correctly without hand-rolling a
  parser.
- **Live anomalies:** WebSocket client (`ws://<api host>/anomalies/live`,
  or `wss://` when the API base URL is `https`), with capped exponential
  backoff reconnect. The connection logic lives entirely in
  `useLiveAnomalies.ts` behind a small `connect()` seam — swapping to SSE
  later (an `EventSource` variant is sketched in a comment at the bottom of
  that file) only touches this one hook.
- **Charts:** hand-rolled inline SVG (no chart library) per the project's
  dataviz skill — line + min/max band + anomaly scatter overlay, crosshair
  tooltip, direct legend, all built on the skill's categorical/status color
  tokens (`src/styles/theme.css`) so light/dark and severity coloring stay
  consistent across the app without pulling in a charting dependency.
