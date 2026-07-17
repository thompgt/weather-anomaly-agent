// Maps the backend's severity/status strings to the dataviz skill's fixed
// status palette. The exact enum values on the wire aren't pinned down yet,
// so this matches by keyword and falls back to "muted" rather than guessing.

export type StatusRole = "good" | "warning" | "serious" | "critical" | "muted";

export function severityToRole(severity: string | undefined | null): StatusRole {
  const s = (severity ?? "").toLowerCase();
  if (s.includes("crit")) return "critical";
  if (s.includes("high") || s.includes("severe") || s.includes("serious")) return "serious";
  if (s.includes("med") || s.includes("warn")) return "warning";
  if (s.includes("low") || s.includes("minor") || s.includes("info")) return "good";
  return "muted";
}

export function statusToRole(status: string | undefined | null): StatusRole {
  const s = (status ?? "").toLowerCase();
  if (s.includes("resolv") || s.includes("closed") || s.includes("dismiss")) return "good";
  if (s.includes("ack")) return "warning";
  if (s.includes("open") || s.includes("new") || s.includes("active")) return "critical";
  return "muted";
}

export function roleLabel(role: StatusRole): string {
  switch (role) {
    case "good":
      return "Good";
    case "warning":
      return "Warning";
    case "serious":
      return "Serious";
    case "critical":
      return "Critical";
    default:
      return "Unknown";
  }
}
