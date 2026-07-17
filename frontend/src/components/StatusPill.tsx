import type { StatusRole } from "../lib/severity";

export function StatusPill({ role, label }: { role: StatusRole; label: string }) {
  return (
    <span className={`pill pill--${role}`}>
      <span className="pill__dot" style={{ background: `var(--status-${role === "muted" ? "muted" : role})` }} />
      {label}
    </span>
  );
}
