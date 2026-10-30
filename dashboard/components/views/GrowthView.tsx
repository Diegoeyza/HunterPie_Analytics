"use client";

import { useState } from "react";
import { fmtDate, fmtTime } from "../../lib/format";
import { ApiState, useApi } from "../../lib/useApi";
import EmptyState, { ScopeEmpty, scopeNames } from "../EmptyState";
import { useFilterOptions } from "../useFilterOptions";
import { MonsterSelect, StarsSelect, WeaponSelect } from "../FilterBar";

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
  early_dps?: number;
  late_dps?: number;
  median_dps?: number;
  best_dps?: number;
  slope_per_hunt?: number;
  slope_pct_per_hunt?: number;
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
  mode?: GrowthMode;
  min_instances?: number;
  groups: MonsterGroup[];
}

interface TopHunterData {
  top_hunters: PlayerImprovementData[];
  mode?: GrowthMode;
  min_instances?: number;
}

type GrowthData = PlayerImprovementData | TopHunterData;

/** Ways to measure growth inside a monster/stars group. All damage-based;
 *  they differ in how much one lucky or awful hunt can swing the answer. */
type GrowthMode = "first_last" | "edge_medians" | "trend";

const GROWTH_MODES: Record<GrowthMode, { label: string; note: string }> = {
  first_last: {
    label: "First → last",
    note: "Compares the first and the newest hunt of each group — what the tab always showed, and the most sensitive to one lucky or one bad hunt.",
  },
  edge_medians: {
    label: "First 3 vs last 3",
    note: "Compares the first and last hunts of each group by median (up to three each, never the same hunt twice), so one outlier at either end is far less decisive than in first → last.",
  },
  trend: {
    label: "Trend fit",
    note: "Fits a straight line through every hunt in the group and reports the change across its span — uses all the evidence instead of two endpoints.",
  },
};

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
  mode, setMode, minHunts, setMinHunts,
}: {
  weapon: string; setWeapon: (v: string) => void;
  monster: string; setMonster: (v: string) => void;
  stars: string; setStars: (v: string) => void;
  topN: string; setTopN: (v: string) => void; showTopN: boolean;
  mode: GrowthMode; setMode: (v: GrowthMode) => void;
  minHunts: string; setMinHunts: (v: string) => void;
}) {
  const opts = useFilterOptions();
  return (
    <div className="filters">
      <WeaponSelect value={weapon} onChange={setWeapon} opts={opts} />
      <MonsterSelect value={monster} opts={opts}
        onChange={(v) => { setMonster(v); setStars(""); }} />
      <StarsSelect value={stars} onChange={setStars} monster={monster} opts={opts} />
      <div className="seg" role="group" aria-label="Growth measure">
        {(Object.keys(GROWTH_MODES) as GrowthMode[]).map((m) => (
          <button
            key={m} type="button"
            className={mode === m ? "on" : ""}
            aria-pressed={mode === m}
            title={GROWTH_MODES[m].note}
            onClick={() => setMode(m)}
          >
            {GROWTH_MODES[m].label}
          </button>
        ))}
      </div>
      <label>Min hunts
        <select value={minHunts} onChange={(e) => setMinHunts(e.target.value)}>
          <option value="2">2</option>
          <option value="3">3</option>
          <option value="5">5</option>
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

export default function GrowthView({ scope, variantId, weaponName, clearScope, setScope, partySize, includeFailed }: { scope: number[]; variantId: number | string | null; weaponName: string | null; clearScope: () => void; setScope: (ids: number[]) => void; partySize: number | null; includeFailed: boolean }) {
  const opts = useFilterOptions();
  const [weapon, setWeapon] = useState("");
  const [monster, setMonster] = useState("");
  const [stars, setStars] = useState("");
  const [topN, setTopN] = useState("5");
  const [mode, setMode] = useState<GrowthMode>("first_last");
  const [minHunts, setMinHunts] = useState("2");

  const selectedPlayerId = scope.length === 1 ? scope[0] : null;
  const isTopMode = selectedPlayerId === null;

  const { data, error, loading } = useApi<GrowthData>("/progress/improvement", {
    ...(selectedPlayerId !== null ? { player_id: selectedPlayerId }
      : scope.length > 1 ? { player_ids: scope.join(",") } : {}),
    ...(weapon && { weapon_id: Number(weapon) }),
    ...(weaponName && { weapon_name: weaponName }),
    ...(monster && { monster_id: Number(monster) }),
    ...(stars && { stars: Number(stars) }),
    ...(variantId !== null && { variant_id: variantId }),
    ...(partySize != null && { players: partySize }),
    ...(includeFailed && { include_failed: true }),
    ...(isTopMode && { top_n: Number(topN) }),
    mode,
    min_instances: Number(minHunts),
  });

  const filterBar = (
    <GrowthFilters weapon={weapon} setWeapon={setWeapon} monster={monster} setMonster={setMonster}
      stars={stars} setStars={setStars} topN={topN} setTopN={setTopN} showTopN={isTopMode}
      mode={mode} setMode={setMode} minHunts={minHunts} setMinHunts={setMinHunts} />
  );

  if (error || loading || !data) {
    return (
      <div className="card">
        {filterBar}
        <ApiState error={error} loading={loading || !data} />
      </div>
    );
  }

  // Guard against scope/data shape mismatch mid-transition.
  const wantPlayer = selectedPlayerId !== null;
  if (wantPlayer !== isPlayerData(data)) {
    return (
      <div className="card">
        {filterBar}
        <p>Loading growth analytics…</p>
      </div>
    );
  }

  if (isPlayerData(data)) {
    const pData = data;
    // Label the payload that is on screen, not the pending filter: useApi
    // keeps the old data while the new mode loads.
    const shownMode = pData.mode ?? mode;
    const shownMin = pData.min_instances ?? Number(minHunts);
    if (!pData.groups || pData.groups.length === 0) {
      return (
        <div className="card">
          {filterBar}
          <ScopeEmpty names={scopeNames(scope, opts?.players)} onClear={clearScope}>
            <p>No monster/star groups with at least {minHunts} hunts found for this hunter with these filters.</p>
          </ScopeEmpty>
        </div>
      );
    }

    const overallPositive = pData.overall_pct_improvement >= 0;

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        <div className="card">
          {filterBar}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "24px 24px 8px", gap: "16px", flexWrap: "wrap" }}>
            <div>
              <h2 style={{ margin: 0, fontSize: "1.5rem" }}>{pData.player_name}&apos;s Growth &amp; Improvement</h2>
              <p style={{ margin: "6px 0 0", color: "var(--muted)", maxWidth: "70ch" }}>
                Instance-weighted growth across {pData.qualifying_groups_count} monster &amp; star
                group{pData.qualifying_groups_count === 1 ? "" : "s"} (≥{shownMin} hunts each).{" "}
                {GROWTH_MODES[shownMode].note}
              </p>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "2rem", fontWeight: "bold", color: overallPositive ? "var(--good)" : "var(--bad)" }}>
                {overallPositive ? "+" : ""}{pData.overall_pct_improvement}%
              </div>
              <div style={{ fontSize: "0.85rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Weighted growth
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0, marginBottom: "16px" }}>Monster &amp; Star Groups (≥{shownMin} hunts)</h3>
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
                    <div>
                      {shownMode === "edge_medians"
                        ? <>First 3: <strong style={{ color: "var(--text)" }}>{g.early_dps ?? "—"}</strong> → Last 3: <strong style={{ color: "var(--text)" }}>{g.late_dps ?? "—"}</strong></>
                        : shownMode === "trend"
                          ? <>Fit: <strong style={{ color: "var(--text)" }}>{g.slope_pct_per_hunt != null ? `${g.slope_pct_per_hunt >= 0 ? "+" : ""}${g.slope_pct_per_hunt}%/hunt` : "—"}</strong> · {g.instances} hunts</>
                          : <>First: <strong style={{ color: "var(--text)" }}>{g.first_dps}</strong> → Latest: <strong style={{ color: "var(--text)" }}>{g.latest_dps}</strong></>}
                    </div>
                    <div>Median: <strong style={{ color: "var(--text)" }}>{g.median_dps ?? "—"}</strong> · Best: <strong style={{ color: "var(--text)" }}>{g.best_dps ?? "—"}</strong></div>
                    <div>Slope: <strong style={{ color: "var(--text)" }}>{g.slope_per_hunt != null ? `${g.slope_per_hunt >= 0 ? "+" : ""}${g.slope_per_hunt}/hunt` : "—"}</strong></div>
                    <div>Clear: <strong style={{ color: "var(--text)" }}>{g.first_clear_s != null ? `${fmtTime(g.first_clear_s)} → ${fmtTime(g.latest_clear_s)}` : "—"}</strong>
                      {g.clear_pct_improvement != null && g.first_clear_s ? (
                        <span style={{ color: clearPositive ? "var(--good)" : "var(--bad)" }}> ({clearPositive ? "+" : ""}{g.clear_pct_improvement}% faster)</span>
                      ) : null}
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "8px", overflowX: "auto", paddingBottom: "4px" }}>
                    {g.hunts.map((h, hIdx) => (
                      <div key={h.hunt_id} title={`Hunt #${h.hunt_id} (${fmtDate(h.started_at)}): ${Math.round(h.dps * 10) / 10} DPS${h.clear_s ? `, ${fmtTime(h.clear_s)}` : ""}`}
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
  const shownMode = topData.mode ?? mode;
  const shownMin = topData.min_instances ?? Number(minHunts);
  if (!topData.top_hunters || topData.top_hunters.length === 0) {
    if (scope.length > 0) {
      return (
        <div className="card">
          {filterBar}
          <ScopeEmpty names={scopeNames(scope, opts?.players)} onClear={clearScope}>
            <p>No multi-hunt monster/star groups for these hunters with these filters.</p>
          </ScopeEmpty>
        </div>
      );
    }
    return (
      <div className="card">
        {filterBar}
        <EmptyState what="hunter improvement data">
          <p>No multi-instance monster/star hunt records found across players.</p>
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="card">
      {filterBar}
      <h2 style={{ marginTop: 0, marginBottom: "8px" }}>Top Hunters by Growth</h2>
      <p style={{ color: "var(--muted)", marginTop: 0, marginBottom: "20px" }}>
        Instance-weighted growth across monster &amp; star groups with ≥{shownMin} hunts.{" "}
        {GROWTH_MODES[shownMode].note}{" "}
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
                    {hunter.qualifying_groups_count} monster/star groups (≥{shownMin} hunts)
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
