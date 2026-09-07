"use client";

import { useEffect, useState } from "react";
import { apiGet, type Health } from "../lib/api";
import { TABS, type ViewCtx } from "../lib/registry";
import ScopeBar, { loadScope } from "../components/ScopeBar";
import ThemeToggle from "../components/ThemeToggle";

const SCOPE_KEY = "hp.scope";

export default function Home() {
  const [tab, setTab] = useState(TABS[0].id);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [scope, setScope] = useState<number[]>([]);
  const [scopeReady, setScopeReady] = useState(false);

  useEffect(() => {
    setScope(loadScope());
    setScopeReady(true);
    apiGet<Health>("/health")
      .then(setHealth)
      .catch((e: Error) => setHealthError(e.message));
  }, []);

  const changeScope = (ids: number[]) => {
    setScope(ids);
    try {
      localStorage.setItem(SCOPE_KEY, JSON.stringify(ids));
    } catch { /* private mode: scope just won't persist */ }
  };

  const active = TABS.find((t) => t.id === tab) ?? TABS[0];
  const ctx: ViewCtx = { scope };

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
        <ThemeToggle />
      </header>
      {scopeReady && <ScopeBar scope={scope} onScope={changeScope} />}
      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={t.id === tab ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.title}
          </button>
        ))}
      </nav>
      <main>
        <p className="blurb">{active.blurb}</p>
        {active.render(ctx)}
      </main>
    </>
  );
}
