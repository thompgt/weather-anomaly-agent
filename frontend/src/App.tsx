import { useState } from "react";
import { DashboardView } from "./views/DashboardView";
import { AlertsView } from "./views/AlertsView";
import { ReportsView } from "./views/ReportsView";
import { ChatView } from "./views/ChatView";

type Tab = "dashboard" | "alerts" | "reports" | "chat";

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "dashboard", label: "Dashboard", icon: "\u{1F4C8}" },
  { id: "alerts", label: "Alerts", icon: "\u{1F6A8}" },
  { id: "reports", label: "Reports", icon: "\u{1F4C4}" },
  { id: "chat", label: "Chat", icon: "\u{1F4AC}" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div className="app-shell">
      <nav className="app-nav" aria-label="Primary">
        <div className="app-nav__brand">
          Weather Anomaly Agent
          <span className="app-nav__brand-sub">Time series monitoring</span>
        </div>
        {TABS.map((t) => (
          <button
            key={t.id}
            className="app-nav__item"
            aria-current={tab === t.id ? "page" : undefined}
            onClick={() => setTab(t.id)}
          >
            <span aria-hidden="true">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </nav>
      <main className="app-main">
        {tab === "dashboard" && <DashboardView />}
        {tab === "alerts" && <AlertsView />}
        {tab === "reports" && <ReportsView />}
        {tab === "chat" && <ChatView />}
      </main>
    </div>
  );
}
