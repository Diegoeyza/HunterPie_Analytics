"use client";

import { useEffect, useState } from "react";
import type { Health } from "../lib/api";
import { useApi } from "../lib/useApi";
import { apiInvalidate } from "../lib/api";
import { parseIds, readParam, writeParams } from "../lib/url";
import { TABS, type ViewCtx } from "../lib/registry";
import ScopeBar, { DEFAULT_PARTY_SIZE, loadParty, loadScope, loadVariant, storeParty, storeScope, storeVariant } from "../components/ScopeBar";
import HuntsManager from "../components/HuntsManager";
import ImportButton from "../components/ImportButton";
import ThemeToggle from "../components/ThemeToggle";
import { ToastProvider } from "../components/Toast";

const TAB_IDS = new Set(TABS.map((t) => t.id));

/** Read initial global state: URL params win (shareable links), then
 *  localStorage, then defaults. */
function initialTab(): string {
  const t = readParam("tab");
  return t && TAB_IDS.has(t) ? t : TABS[0].id;
}

function initialScope(): number[] {
  const raw = readParam("scope");
  if (raw !== null) return parseIds(raw);
  return loadScope();
}

function initialParty(): number | null {
  const raw = readParam("party");
  if (raw === null) return loadParty();
  if (raw === "all") return null;
  const n = Number(raw);
  return Number.isInteger(n) && n >= 1 && n <= 8 ? n : loadParty();
}

export default function Home() {
  // Defaults first (server prerender); URL/localStorage sync in the
  // mount effect below — reading window.location during render would
  // hydrate-mismatch on shared links (?tab=hunts prerenders as tab=0).
  const [tab, setTab] = useState(TABS[0].id);
  const [scope, setScope] = useState<number[]>([]);
  const [variantId, setVariantId] = useState<number | string | null>(null);
  const [partySize, setPartySize] = useState<number | null>(DEFAULT_PARTY_SIZE);
  const [scopeReady, setScopeReady] = useState(false);
  const healthQ = useApi<Health>("/health");

  useEffect(() => {
    setTab(initialTab());
    const ids = initialScope();
    setScope(ids);
    setPartySize(initialParty());
    // A persisted variant only survives with the same single-hunter scope.
    setVariantId(ids.length === 1 ? loadVariant() : null);
    setScopeReady(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const changeTab = (id: string) => {
    setTab(id);
    writeParams({ tab: id === TABS[0].id ? null : id });
  };

  const changeScope = (ids: number[]) => {
    setScope(ids);
    if (ids.length !== 1) changeVariant(null);
    storeScope(ids);
    writeParams({ scope: ids.length > 0 ? ids.join(",") : null });
  };

  const changeVariant = (id: number | string | null) => {
    setVariantId(id);
    storeVariant(id);
  };

  const changeParty = (size: number | null) => {
    setPartySize(size);
    storeParty(size);
    writeParams({ party: size === null ? "all" : String(size) });
  };

  const active = TABS.find((t) => t.id === tab) ?? TABS[0];
  const ctx: ViewCtx = { scope, variantId: scope.length === 1 ? variantId : null, clearScope: () => changeScope([]), setScope: changeScope, partySize };
  const health = healthQ.data;
  const versions = health?.hunterpie_version ?? health?.game_version
    ? `HunterPie ${health?.hunterpie_version ?? "?"} · game ${health?.game_version ?? "?"}`
    : undefined;

  return (
    <ToastProvider>
      <header className="topbar">
        <h1>HunterPie Analytics</h1>
        <span className={`status-dot ${health ? "on" : ""}`} />
        <span className="status-text" title={versions}>
          {health
            ? `ingestion online · ${health.hunts} hunts`
            : (healthQ.error ?? "connecting…")}
        </span>
        <ImportButton onImported={() => { apiInvalidate(); healthQ.refetch(); }} />
        <HuntsManager />
        <ThemeToggle />
      </header>
      {scopeReady && (
        <ScopeBar scope={scope} onScope={changeScope}
          variantId={scope.length === 1 ? variantId : null}
          onVariant={changeVariant}
          partySize={partySize} onParty={changeParty} />
      )}
      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={t.id === tab ? "active" : ""} onClick={() => changeTab(t.id)}>
            {t.title}
          </button>
        ))}
      </nav>
      <main>
        <p className="blurb">{active.blurb}</p>
        {active.render(ctx)}
      </main>
    </ToastProvider>
  );
}

// Re-export for tests/other modules that keyed off the api cache directly.