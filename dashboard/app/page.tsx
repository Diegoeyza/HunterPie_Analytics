"use client";

import { useEffect, useState } from "react";
import { apiGet, type Health } from "../lib/api";
import { TABS, type ViewCtx } from "../lib/registry";
import ScopeBar, { loadScope, loadVariant, storeVariant } from "../components/ScopeBar";
import HuntsManager from "../components/HuntsManager";
import ImportButton from "../components/ImportButton";
import ThemeToggle from "../components/ThemeToggle";

const SCOPE_KEY = "hp.scope";

export default function Home() {
  const [tab, setTab] = useState(TABS[0].id);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [scope, setScope] = useState<number[]>([]);
  const [variantId, setVariantId] = useState<number | null>(null);
  const [scopeReady, setScopeReady] = useState(false);

  useEffect(() => {
    const ids = loadScope();
    setScope(ids);
    // A persisted variant only survives with the same single-hunter scope.
    setVariantId(ids.length === 1 ? loadVariant() : null);
    setScopeReady(true);
    apiGet<Health>("/health")
      .then(setHealth)
      .catch((e: Error) => setHealthError(e.message));
  }, []);

  const changeScope = (ids: number[]) => {
    setScope(ids);
    if (ids.length !== 1) changeVariant(null);
    try {
      localStorage.setItem(SCOPE_KEY, JSON.stringify(ids));
    } catch { /* private mode: scope just won't persist */ }
  };

  const changeVariant = (id: number | null) => {
    setVariantId(id);
    storeVariant(id);
  };

  const active = TABS.find((t) => t.id === tab) ?? TABS[0];
  const ctx: ViewCtx = { scope, variantId: scope.length === 1 ? variantId : null, clearScope: () => changeScope([]), setScope: changeScope };

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
        <ImportButton onImported={setHealth} />
        <HuntsManager />
        <ThemeToggle />
      </header>
      {scopeReady && (
        <ScopeBar scope={scope} onScope={changeScope}
          variantId={scope.length === 1 ? variantId : null}
          onVariant={changeVariant} />
      )}
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
