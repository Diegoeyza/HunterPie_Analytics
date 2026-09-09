"use client";

import { useEffect, useState } from "react";
import { apiGet } from "../../lib/api";
import EmptyState, { ScopeEmpty, scopeNames } from "../EmptyState";
import { useFilterOptions } from "../useFilterOptions";
import SearchSelect from "../SearchSelect";

interface HuntPoint {
  hunt_id: number;
  started_at: string;
  dps: number;
  clear_s: number | null;
}

interface MonsterGroup {
  monster_id: number;
  monster_name: string;
  stars: number | null;
  instances: number;
  first_dps: number;
  latest_dps: number;
  median_dps?: number;
  best_dps?: number;
  slope_per_hunt?: number;
  pct_improvement: number;
  first_clear_s?: number | null;
  latest_clear_s?: number | null;
  clear_pct_improvement?: number;
  hunts: HuntPoint[];
}

interface PlayerImprovementData {
  player_id: number;
  player_name: string;
  overall_pct_improvement: number;
  qualifying_groups_count: number;
  groups: MonsterGroup[];
}

interface TopHunterData {
  top_hunters: PlayerImprovementData[];
}

type GrowthData = PlayerImprovementData | TopHunterData;

function isPlayerData(d: GrowthData): d is PlayerImprovementData {
  return (d as PlayerImprovementData).groups !== undefined;
}

function Sparkline({ vals }: { vals: number[] }) {
  if (vals.length < 2) return null;
  const w = 120;
  const h = 36;
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const pts = vals
    .map((v, i) => `${((i / (vals.length - 1)) * w).toFixed(1)},${(h - 4 - ((v - min) / span) * (h - 8)).toFixed(1)}`)
    .join(" ");
  const up = vals[vals.length - 1] >= vals[0];
  return (
    <svg width={w} height={h} role="img" aria-label={`DPS trend ${up ? "up" : "down"}`}>
      <polyline points={pts} fill="none" stroke="var(--accent)" strokeWidth="2" />
      <circle cx={w} cy={h - 4 - ((vals[vals.length - 1] - min) / span) * (h - 8)} r="3" fill="var(--accent)" />
    </svg>
  );
}

function GrowthFilters({
  weapon, setWeapon, monster, setMonster, stars, setStars, topN, setTopN, showTopN,
}: {
  weapon: string; setWeapon: (v: string) => void;
  monster: string; setMonster: (v: string) => void;
  stars: string; setStars: (v: string) => void;
  topN: string; setTopN: (v: string) => void; showTopN: boolean;
}) {
  const opts = useFilterOptions();
  return (
    <div className="filters">
      <SearchSelect
        label="Weapon"
        value={weapon}
        options={(opts?.weapons ?? []).map((w) => ({ value: String(w.id), label: w.name }))}
        onChange={setWeapon}
      />
      <SearchSelect
        label="Monster"
        value={monster}
        options={(opts?.monsters ?? []).map((m) => ({ value: String(m.id), label: m.name }))}
        onChange={(v) => { setMonster(v); setStars(""); }}
      />
      <label>Stars
        <select value={stars} onChange={(e) => setStars(e.target.value)}>
          <option value="">All</option>
          {(monster ? (opts?.monster_stars[Number(monster)] ?? opts?.stars ?? []) : opts?.stars ?? []).map((s) => (
            <option key={s} value={s}>{s}★</option>
          ))}
        </select>
      </label>
      {showTopN && (
        <label>Top
          <select value={topN} onChange={(e) => setTopN(e.target.value)}>
            <option value="3">3</option>
            <option value="5">5</option>
            <option value="10">10</option>
          </select>
        </label>
      )}
    </div>
  );
}

export default function GrowthView({ scope, variantId, clearScope, setScope }: { scope: number[]; variantId: number | null; clearScope: () => void; setScope: (ids: number[]) => void }) {
  const opts = useFilterOptions();
  const [weapon, setWeapon] = useState("");
  const [monster, setMonster] = useState("");
  const [stars, setStars] = useState("");
  const [topN, setTopN] = useState("5");
  const [data, setData] = useState<GrowthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const selectedPlayerId = scope.length === 1 ? scope[0] : null;
  const scopeKey = scope.join(",");
  const isTopMode = selectedPlayerId === null;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    const params: Record<string, string | number> = {};
    if (selectedPlayerId !== null) params.player_id = selectedPlayerId;
    else if (scope.length > 1) params.player_ids = scopeKey;
    if (weapon) params.weapon_id = Number(weapon);
    if (monster) params.monster_id = Number(monster);
    if (stars) params.stars = Number(stars);
    if (variantId !== null) params.variant_id = variantId;
    if (isTopMode) params.top_n = Number(topN);
    apiGet<GrowthData>("/progress/improvement", params)
      .then((d) => { if (!cancelled) { setData(d); setLoading(false); } })
      .catch((e: Error) => { if (!cancelled) { setError(e.message); setLoading(false); } });
    return () => { cancelled = true; };
  }, [selectedPlayerId, scopeKey, weapon, monster, stars, topN, variantId, isTopMode]);

  if (error) return <p className="error">{error} — is the API running on :8000?</p>;
  if (loading || !data) return <p>Loading growth analytics…</p>;

  // Guard against scope/data shape mismatch mid-transition.
  const wantPlayer = selectedPlayerId !== null;
  if (wantPlayer !== isPlayerData(data)) return <p>Loading growth analytics…</p>;

  if (isPlayerData(data)) {
    const pData = data;
    const filters = (
      <GrowthFilters weapon={weapon} setWeapon={setWeapon} monster={monster} setMonster={setMonster}
        stars={stars} setStars={setStars} topN={topN} setTopN={setTopN} showTopN={false} />
    );
    if (!pData.groups || pData.groups.length === 0) {
      return (
        <div className="card">
          {filters}
          <ScopeEmpty names={scopeNames(scope, opts?.players)} onClear={clearScope}>
            <p>No monster/star categories with multiple hunt instances (&gt;1 instance) found for this hunter with these filters.</p>
          </ScopeEmpty>
        </div>
      );
    }

    const overallPositive = pData.overall_pct_improvement >= 0;

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        <div className="card">
          {filters}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "24px 24px 8px", gap: "16px", flexWrap: "wrap" }}>
            <div>
              <h2 style={{ margin: 0, fontSize: "1.5rem" }}>{pData.player_name}&apos;s Growth &amp; Improvement</h2>
              <p style={{ margin: "6px 0 0", color: "var(--muted)" }}>
                Instance-weighted DPS change across {pData.qualifying_groups_count} monster &amp; star categories (&gt;1 hunt each).
              </p>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "2rem", fontWeight: "bold", color: overallPositive ? "var(--good)" : "var(--bad)" }}>
                {overallPositive ? "+" : ""}{pData.overall_pct_improvement}%
              </div>
              <div style={{ fontSize: "0.85rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Weighted DPS change
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0, marginBottom: "16px" }}>Monster &amp; Star Categories (&gt;1 hunt)</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {pData.groups.map((g, idx) => {
              const positive = g.pct_improvement >= 0;
              const clearPositive = (g.clear_pct_improvement ?? 0) >= 0;
              return (
                <div key={`${g.monster_id}-${g.stars ?? "na"}-${idx}`} style={{ background: "var(--panel-2)", border: "1px solid var(--border)", borderRadius: "8px", padding: "16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", gap: "12px", flexWrap: "wrap" }}>
                    <div>
                      <span style={{ fontSize: "1.1rem", fontWeight: "600", color: "var(--text)" }}>{g.monster_name}</span>
                      {g.stars != null && <span style={{ marginLeft: "8px", background: "var(--panel)", border: "1px solid var(--border)", padding: "2px 8px", borderRadius: "4px", fontSize: "0.85rem" }}>{g.stars}★</span>}
                      <span style={{ marginLeft: "12px", fontSize: "0.85rem", color: "var(--muted)" }}>{g.instances} hunts</span>
                    </div>
                    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      <Sparkline vals={g.hunts.map((h) => h.dps)} />
                      <div style={{ background: positive ? "color-mix(in srgb, var(--good) 15%, transparent)" : "color-mix(in srgb, var(--bad) 15%, transparent)", color: positive ? "var(--good)" : "var(--bad)", padding: "4px 10px", borderRadius: "6px", fontWeight: "bold", fontSize: "0.95rem" }}>
                        {positive ? "+" : ""}{g.pct_improvement}% DPS
                      </div>
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem", color: "var(--muted)", marginBottom: "10px", gap: "12px", flexWrap: "wrap" }}>
                    <div>First: <strong style={{ color: "var(--text)" }}>{g.first_dps}</strong> → Latest: <strong style={{ color: "var(--text)" }}>{g.latest_dps}</strong></div>
                    <div>Median: <strong style={{ color: "var(--text)" }}>{g.median_dps ?? "—"}</strong> · Best: <strong style={{ color: "var(--text)" }}>{g.best_dps ?? "—"}</strong></div>
                    <div>Slope: <strong style={{ color: "var(--text)" }}>{g.slope_per_hunt != null ? `${g.slope_per_hunt >= 0 ? "+" : ""}${g.slope_per_hunt}/hunt` : "—"}</strong></div>
                    <div>Clear: <strong style={{ color: "var(--text)" }}>{g.first_clear_s != null ? `${g.first_clear_s}s → ${g.latest_clear_s}s` : "—"}</strong>
                      {g.clear_pct_improvement != null && g.first_clear_s ? (
                        <span style={{ color: clearPositive ? "var(--good)" : "var(--bad)" }}> ({clearPositive ? "+" : ""}{g.clear_pct_improvement}% faster)</span>
                      ) : null}
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "8px", overflowX: "auto", paddingBottom: "4px" }}>
                    {g.hunts.map((h, hIdx) => (
                      <div key={h.hunt_id} title={`Hunt #${h.hunt_id} (${h.started_at.slice(0, 10)}): ${Math.round(h.dps * 10) / 10} DPS${h.clear_s ? `, ${Math.round(h.clear_s)}s` : ""}`}
                        style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: "60px", background: "var(--panel)", padding: "6px 8px", borderRadius: "6px", border: "1px solid var(--border)" }}>
                        <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>#{h.hunt_id}{hIdx === 0 ? " ·1st" : hIdx === g.hunts.length - 1 ? " ·new" : ""}</span>
                        <span style={{ fontSize: "0.9rem", fontWeight: "600", color: "var(--accent)" }}>{Math.round(h.dps * 10) / 10}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  const topData = data as TopHunterData;
  const filters = (
    <GrowthFilters weapon={weapon} setWeapon={setWeapon} monster={monster} setMonster={setMonster}
      stars={stars} setStars={setStars} topN={topN} setTopN={setTopN} showTopN />
  );
  if (!topData.top_hunters || topData.top_hunters.length === 0) {
    if (scope.length > 0) {
      return (
        <div className="card">
          {filters}
          <ScopeEmpty names={scopeNames(scope, opts?.players)} onClear={clearScope}>
            <p>No multi-hunt monster/star groups for these hunters with these filters.</p>
          </ScopeEmpty>
        </div>
      );
    }
    return (
      <div className="card">
        {filters}
        <EmptyState what="hunter improvement data">
          <p>No multi-instance monster/star hunt records found across players.</p>
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="card">
      {filters}
      <h2 style={{ marginTop: 0, marginBottom: "8px" }}>Top Hunters by DPS Improvement</h2>
      <p style={{ color: "var(--muted)", marginTop: 0, marginBottom: "20px" }}>
        Instance-weighted DPS change across monster &amp; star categories with &gt;1 hunt.
        {scope.length > 1 ? ` Scoped to ${scope.length} hunters — ` : " "}
        {scope.length > 1 ? <button type="button" className="scope-clear" onClick={clearScope}>Clear hunter scope</button> : "Select a hunter for the full breakdown."}
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {topData.top_hunters.map((hunter, rank) => {
          const positive = hunter.overall_pct_improvement >= 0;
          return (
            <button
              key={hunter.player_id}
              type="button"
              onClick={() => setScope([hunter.player_id])}
              aria-label={`View ${hunter.player_name} growth`}
              style={{ background: "var(--panel-2)", border: "1px solid var(--border)", borderRadius: "8px", padding: "20px", display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer", textAlign: "left", width: "100%", color: "inherit", font: "inherit" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--accent)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border)"; }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                <span style={{ fontSize: "1.5rem", fontWeight: "bold", color: rank === 0 ? "var(--accent)" : "var(--muted)", minWidth: "32px", textAlign: "center" }}>
                  #{rank + 1}
                </span>
                <span>
                  <span style={{ margin: 0, fontSize: "1.2rem", color: "var(--text)", fontWeight: 600, display: "block" }}>{hunter.player_name}</span>
                  <span style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: "0.9rem", display: "block" }}>
                    {hunter.qualifying_groups_count} monster/star groups (&gt;1 hunt)
                  </span>
                </span>
              </span>

              <span style={{ textAlign: "right" }}>
                <span style={{ fontSize: "1.8rem", fontWeight: "bold", color: positive ? "var(--good)" : "var(--bad)", display: "block" }}>
                  {positive ? "+" : ""}{hunter.overall_pct_improvement}%
                </span>
                <span style={{ fontSize: "0.8rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em", display: "block" }}>
                  Weighted growth
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
