"use client";

import { useEffect, useState } from "react";
import { apiGet, type Health } from "../lib/api";
import { TABS } from "../lib/registry";

export default function Home() {
  const [tab, setTab] = useState(TABS[0].id);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<Health>("/health")
      .then(setHealth)
      .catch((e: Error) => setHealthError(e.message));
  }, []);

  const active = TABS.find((t) => t.id === tab) ?? TABS[0];

  return (
    <>
      <header className="topbar">
        <h1>HunterPie Analytics</h1>
        <span className={`status-dot ${health ? "on" : ""}`} />
        <span className="status-text">
          {health
            ? `ingestion online · ${health.hunts} hunts`
            : (healthError ?? "connecting…")}
        </span>
      </header>
      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={t.id === tab ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.title}
          </button>
        ))}
      </nav>
      <main>
        <p className="blurb">{active.blurb}</p>
        {active.render()}
      </main>
    </>
  );
}
