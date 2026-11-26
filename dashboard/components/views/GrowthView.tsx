"use client";

import { useState } from "react";
import { fmtClearTime, fmtDate, fmtDps } from "../../lib/format";
import { ApiState, useApi } from "../../lib/useApi";
import EmptyState, { ScopeEmpty, scopeNames } from "../EmptyState";
import { useFilterOptions } from "../useFilterOptions";
import { MonsterSelect, StarsSelect, WeaponSelect } from "../FilterBar";
import { useT, type TFn } from "@/lib/i18n";
import { monsterName } from "@/lib/names";

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

function growthModes(t: TFn): Record<GrowthMode, { label: string; note: string }> {
  return {
    first_last: {
      label: t("growth.mode.firstLast.label"),
      note: t("growth.mode.firstLast.note"),
    },
    edge_medians: {
      label: t("growth.mode.edgeMedians.label"),
      note: t("growth.mode.edgeMedians.note"),
    },
    trend: {
      label: t("growth.mode.trend.label"),
      note: t("growth.mode.trend.note"),
    },
  };
}

function isPlayerData(d: GrowthData): d is PlayerImprovementData {
  return (d as PlayerImprovementData).groups !== undefined;
}

function Sparkline({ vals }: { vals: number[] }) {
  const { t } = useT();
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
    <svg width={w} height={h} role="img" aria-label={up ? t("growth.sparkline.up") : t("growth.sparkline.down")}>
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
  const { t } = useT();
  const GROWTH_MODES = growthModes(t);
  const opts = useFilterOptions();
  return (
    <div className="filters">
      <WeaponSelect value={weapon} onChange={setWeapon} opts={opts} />
      <MonsterSelect value={monster} opts={opts}
        onChange={(v) => { setMonster(v); setStars(""); }} />
      <StarsSelect value={stars} onChange={setStars} monster={monster} opts={opts} />
      <div className="seg" role="group" aria-label={t("growth.measureAria")}>
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
      <label>{t("growth.filter.minHunts")}
        <select value={minHunts} onChange={(e) => setMinHunts(e.target.value)}>
          <option value="2">2</option>
          <option value="3">3</option>
          <option value="5">5</option>
        </select>
      </label>
      {showTopN && (
        <label>{t("growth.filter.top")}
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
  const { t } = useT();
  const GROWTH_MODES = growthModes(t);
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
        <p>{t("growth.loading")}</p>
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
            <p>{t("growth.empty.player", { min: minHunts })}</p>
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
              <h2 style={{ margin: 0, fontSize: "1.5rem" }}>{t("growth.player.heading", { name: pData.player_name })}</h2>
              <p style={{ margin: "6px 0 0", color: "var(--muted)", maxWidth: "70ch" }}>
                {t(pData.qualifying_groups_count === 1 ? "growth.summary.one" : "growth.summary.other", { n: pData.qualifying_groups_count, min: shownMin })}{" "}
                {GROWTH_MODES[shownMode].note}
              </p>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "2rem", fontWeight: "bold", color: overallPositive ? "var(--good)" : "var(--bad)" }}>
                {overallPositive ? "+" : ""}{pData.overall_pct_improvement}%
              </div>
              <div style={{ fontSize: "0.85rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                {t("growth.weighted")}
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0, marginBottom: "16px" }}>{t("growth.groups.heading", { min: shownMin })}</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {pData.groups.map((g, idx) => {
              const positive = g.pct_improvement >= 0;
              const clearPositive = (g.clear_pct_improvement ?? 0) >= 0;
              return (
                <div key={`${g.monster_id}-${g.stars ?? "na"}-${idx}`} style={{ background: "var(--panel-2)", border: "1px solid var(--border)", borderRadius: "8px", padding: "16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", gap: "12px", flexWrap: "wrap" }}>
                    <div>
                      <span style={{ fontSize: "1.1rem", fontWeight: "600", color: "var(--text)" }}>{monsterName(g.monster_name, g.monster_id)}</span>
                      {g.stars != null && <span style={{ marginLeft: "8px", background: "var(--panel)", border: "1px solid var(--border)", padding: "2px 8px", borderRadius: "4px", fontSize: "0.85rem" }}>{g.stars}★</span>}
                      <span style={{ marginLeft: "12px", fontSize: "0.85rem", color: "var(--muted)" }}>{t("name.hunts", { n: g.instances })}</span>
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
                        ? <>{t("growth.group.first3")} <strong style={{ color: "var(--text)" }}>{g.early_dps ?? "—"}</strong> → {t("growth.group.last3")} <strong style={{ color: "var(--text)" }}>{g.late_dps ?? "—"}</strong></>
                        : shownMode === "trend"
                          ? <>{t("growth.group.fit")} <strong style={{ color: "var(--text)" }}>{g.slope_pct_per_hunt != null ? `${g.slope_pct_per_hunt >= 0 ? "+" : ""}${g.slope_pct_per_hunt}${t("growth.group.perHuntPct")}` : "—"}</strong> · {t("name.hunts", { n: g.instances })}</>
                          : <>{t("growth.group.first")} <strong style={{ color: "var(--text)" }}>{g.first_dps}</strong> → {t("growth.group.latest")} <strong style={{ color: "var(--text)" }}>{g.latest_dps}</strong></>}
                    </div>
                    <div>{t("growth.group.median")} <strong style={{ color: "var(--text)" }}>{g.median_dps ?? "—"}</strong> · {t("growth.group.best")} <strong style={{ color: "var(--text)" }}>{g.best_dps ?? "—"}</strong></div>
                    <div>{t("growth.group.slope")} <strong style={{ color: "var(--text)" }}>{g.slope_per_hunt != null ? `${g.slope_per_hunt >= 0 ? "+" : ""}${g.slope_per_hunt}${t("growth.group.perHunt")}` : "—"}</strong></div>
                    <div>{t("growth.group.clear")} <strong style={{ color: "var(--text)" }}>{g.first_clear_s != null ? `${fmtClearTime(g.first_clear_s)} → ${fmtClearTime(g.latest_clear_s)}` : "—"}</strong>
                      {g.clear_pct_improvement != null && g.first_clear_s ? (
                        <span style={{ color: clearPositive ? "var(--good)" : "var(--bad)" }}>{t("growth.group.faster", { pct: `${clearPositive ? "+" : ""}${g.clear_pct_improvement}` })}</span>
                      ) : null}
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "8px", overflowX: "auto", paddingBottom: "4px" }}>
                    {g.hunts.map((h, hIdx) => (
                      <div key={h.hunt_id} title={t("growth.group.huntTitle", { id: h.hunt_id, date: fmtDate(h.started_at), dps: fmtDps(h.dps) })
                        + (h.clear_s ? t("growth.group.huntTitleClear", { time: fmtClearTime(h.clear_s) }) : "")}
                        style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: "60px", background: "var(--panel)", padding: "6px 8px", borderRadius: "6px", border: "1px solid var(--border)" }}>
                        <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>#{h.hunt_id}{hIdx === 0 ? t("growth.group.firstTag") : hIdx === g.hunts.length - 1 ? t("growth.group.newTag") : ""}</span>
                        <span style={{ fontSize: "0.9rem", fontWeight: "600", color: "var(--accent)" }}>{fmtDps(h.dps)}</span>
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
            <p>{t("growth.empty.scope")}</p>
          </ScopeEmpty>
        </div>
      );
    }
    return (
      <div className="card">
        {filterBar}
        <EmptyState what={t("growth.empty.none")}>
          <p>{t("growth.empty.hint")}</p>
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="card">
      {filterBar}
      <h2 style={{ marginTop: 0, marginBottom: "8px" }}>{t("growth.top.heading")}</h2>
      <p style={{ color: "var(--muted)", marginTop: 0, marginBottom: "20px" }}>
        {t("growth.top.blurb", { min: shownMin })}{" "}
        {GROWTH_MODES[shownMode].note}{" "}
        {scope.length > 1 ? ` ${t("growth.top.scoped", { n: scope.length })}` : " "}
        {scope.length > 1 ? <button type="button" className="scope-clear" onClick={clearScope}>{t("table.empty.clearScope")}</button> : t("growth.top.select")}
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {topData.top_hunters.map((hunter, rank) => {
          const positive = hunter.overall_pct_improvement >= 0;
          return (
            <button
              key={hunter.player_id}
              type="button"
              onClick={() => setScope([hunter.player_id])}
              aria-label={t("growth.top.view", { name: hunter.player_name })}
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
                    {t(hunter.qualifying_groups_count === 1 ? "growth.top.groups.one" : "growth.top.groups.other", { n: hunter.qualifying_groups_count, min: shownMin })}
                  </span>
                </span>
              </span>

              <span style={{ textAlign: "right" }}>
                <span style={{ fontSize: "1.8rem", fontWeight: "bold", color: positive ? "var(--good)" : "var(--bad)", display: "block" }}>
                  {positive ? "+" : ""}{hunter.overall_pct_improvement}%
                </span>
                <span style={{ fontSize: "0.8rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em", display: "block" }}>
                  {t("growth.weighted")}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
