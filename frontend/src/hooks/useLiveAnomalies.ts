import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "../api/client";
import type { Anomaly } from "../types";

// GET /anomalies/live streams newly-inserted anomaly rows. The contract
// says "assume WebSocket unless you have reason to pick SSE" - we implement
// WebSocket as the live transport, but keep the transport behind a single
// `connect()` seam so swapping to EventSource later only touches this file
// (see the commented SSE variant below `connectWebSocket`).

export type LiveConnectionState = "connecting" | "open" | "closed" | "error";

export interface UseLiveAnomaliesResult {
  liveAnomalies: Anomaly[];
  connectionState: LiveConnectionState;
}

function wsUrl(): string {
  const base = new URL(API_BASE_URL);
  const protocol = base.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${base.host}/anomalies/live`;
}

const RECONNECT_DELAYS_MS = [1000, 2000, 5000, 10000];

export function useLiveAnomalies(maxItems = 20): UseLiveAnomaliesResult {
  const [liveAnomalies, setLiveAnomalies] = useState<Anomaly[]>([]);
  const [connectionState, setConnectionState] = useState<LiveConnectionState>("connecting");
  const attemptRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;

    function scheduleReconnect() {
      if (cancelled) return;
      const delay =
        RECONNECT_DELAYS_MS[Math.min(attemptRef.current, RECONNECT_DELAYS_MS.length - 1)];
      attemptRef.current += 1;
      timerRef.current = setTimeout(connect, delay);
    }

    function connect() {
      if (cancelled) return;
      setConnectionState("connecting");
      try {
        socket = new WebSocket(wsUrl());
      } catch (err) {
        console.warn("[ws] failed to construct WebSocket, will retry", err);
        setConnectionState("error");
        scheduleReconnect();
        return;
      }

      socket.onopen = () => {
        if (cancelled) return;
        attemptRef.current = 0;
        setConnectionState("open");
      };

      socket.onmessage = (event) => {
        if (cancelled) return;
        try {
          const payload = JSON.parse(event.data) as Anomaly | Anomaly[];
          const incoming = Array.isArray(payload) ? payload : [payload];
          setLiveAnomalies((prev) => [...incoming, ...prev].slice(0, maxItems));
        } catch (err) {
          console.warn("[ws] failed to parse /anomalies/live message", err);
        }
      };

      socket.onerror = () => {
        if (cancelled) return;
        setConnectionState("error");
      };

      socket.onclose = () => {
        if (cancelled) return;
        setConnectionState("closed");
        scheduleReconnect();
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      socket?.close();
    };
  }, [maxItems]);

  return { liveAnomalies, connectionState };
}

// --- SSE variant (kept for reference; swap in if the backend ships SSE
// instead of WebSocket - same shape, just replace `connect()` above) ---
//
// function connectSse(onMessage: (a: Anomaly) => void, onStateChange: (s: LiveConnectionState) => void) {
//   const source = new EventSource(`${API_BASE_URL}/anomalies/live`);
//   source.onopen = () => onStateChange("open");
//   source.onerror = () => onStateChange("error");
//   source.onmessage = (event) => onMessage(JSON.parse(event.data));
//   return () => source.close();
// }
