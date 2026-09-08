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
  pct_improvement: number;
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

export default function GrowthView({ scope, variantId, clearScope, setScope }: { scope: number[]; variantId: number | null; clearScope: () => void; setScope: (ids: number[]) => void }) {
  const opts = useFilterOptions();
  const [weapon, setWeapon] = useState("");
  const [data, setData] = useState<PlayerImprovementData | TopHunterData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedPlayerId = scope.length === 1 ? scope[0] : null;

  useEffect(() => {
    setError(null);
    const params: Record<string, string | number> = {};
    if (selectedPlayerId) params.player_id = selectedPlayerId;
    if (weapon) params.weapon_id = Number(weapon);
    apiGet<PlayerImprovementData | TopHunterData>("/progress/improvement", params)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [selectedPlayerId, weapon]);

  if (error) return <p className="error">{error} — is the API running on :8000?</p>;
  if (!data) return <p>Loading growth analytics…</p>;

  // If a hunter is selected (PlayerImprovementData)
  if (selectedPlayerId !== null) {
    const pData = data as PlayerImprovementData;
    if (!pData.groups || pData.groups.length === 0) {
      return (
        <div className="card">
          <div className="filters">
            <SearchSelect
              label="Weapon"
              value={weapon}
              options={(opts?.weapons ?? []).map((w) => ({ value: String(w.id), label: w.name }))}
              onChange={setWeapon}
            />
          </div>
          <ScopeEmpty names={scopeNames(scope, opts?.players)} onClear={clearScope}>
            <p>No monster/star categories with multiple hunt instances (&gt;1 instance) found for this hunter.</p>
          </ScopeEmpty>
        </div>
      );
    }

    const overallPositive = pData.overall_pct_improvement >= 0;

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
        {/* Overall Summary Card */}
        <div className="card">
          <div className="filters">
            <SearchSelect
              label="Weapon"
              value={weapon}
              options={(opts?.weapons ?? []).map((w) => ({ value: String(w.id), label: w.name }))}
              onChange={setWeapon}
            />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "24px" }}>
            <div>
              <h2 style={{ margin: 0, fontSize: "1.5rem" }}>{pData.player_name}&apos;s Growth &amp; Improvement</h2>
              <p style={{ margin: "6px 0 0", color: "#9aa1b2" }}>
                Analyzed across {pData.qualifying_groups_count} monster &amp; star categories (only quests/monsters with &gt;1 instance).
              </p>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "2rem", fontWeight: "bold", color: overallPositive ? "#58b368" : "#e06c75" }}>
                {overallPositive ? "+" : ""}{pData.overall_pct_improvement}%
              </div>
              <div style={{ fontSize: "0.85rem", color: "#9aa1b2", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Overall DPS Improvement
              </div>
            </div>
          </div>
        </div>

        {/* Monster & Star Categories Breakdown */}
        <div className="card">
          <h3 style={{ marginTop: 0, marginBottom: "16px" }}>Monster &amp; Star Categories (&gt;1 instance)</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {pData.groups.map((g, idx) => {
              const positive = g.pct_improvement >= 0;
              return (
                <div key={idx} style={{ background: "#1d2029", border: "1px solid #2c313e", borderRadius: "8px", padding: "16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                    <div>
                      <span style={{ fontSize: "1.1rem", fontWeight: "600", color: "#fff" }}>{g.monster_name}</span>
                      {g.stars && <span style={{ marginLeft: "8px", background: "#2c313e", padding: "2px 8px", borderRadius: "4px", fontSize: "0.85rem" }}>{g.stars}★</span>}
                      <span style={{ marginLeft: "12px", fontSize: "0.85rem", color: "#9aa1b2" }}>{g.instances} hunts</span>
                    </div>
                    <div style={{ background: positive ? "rgba(88, 179, 104, 0.15)" : "rgba(224, 108, 117, 0.15)", color: positive ? "#58b368" : "#e06c75", padding: "4px 10px", borderRadius: "6px", fontWeight: "bold", fontSize: "0.95rem" }}>
                      {positive ? "+" : ""}{g.pct_improvement}% DPS
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem", color: "#9aa1b2", marginBottom: "10px" }}>
                    <div>First Hunt DPS: <strong style={{ color: "#fff" }}>{g.first_dps}</strong></div>
                    <div>Latest Hunt DPS: <strong style={{ color: "#fff" }}>{g.latest_dps}</strong></div>
                  </div>

                  {/* Timeline mini-bars / dots */}
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", overflowX: "auto", paddingBottom: "4px" }}>
                    {g.hunts.map((h, hIdx) => (
                      <div key={hIdx} title={`Hunt #${h.hunt_id} (${h.started_at.slice(0, 10)}): ${Math.round(h.dps * 10) / 10} DPS`}
                        style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: "60px", background: "#242833", padding: "6px 8px", borderRadius: "6px", border: "1px solid #2c313e" }}>
                        <span style={{ fontSize: "0.75rem", color: "#9aa1b2" }}>#{h.hunt_id}</span>
                        <span style={{ fontSize: "0.9rem", fontWeight: "600", color: "#e8b64c" }}>{Math.round(h.dps * 10) / 10}</span>
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

  // If no hunter is selected (Top hunters list)
  const topData = data as TopHunterData;
  if (!topData.top_hunters || topData.top_hunters.length === 0) {
    return (
      <div className="card">
        <div className="filters">
          <SearchSelect
            label="Weapon"
            value={weapon}
            options={(opts?.weapons ?? []).map((w) => ({ value: String(w.id), label: w.name }))}
            onChange={setWeapon}
          />
        </div>
        <EmptyState what="hunter improvement data">
          <p>No multi-instance monster/star hunt records found across players.</p>
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="filters">
        <SearchSelect
          label="Weapon"
          value={weapon}
          options={(opts?.weapons ?? []).map((w) => ({ value: String(w.id), label: w.name }))}
          onChange={setWeapon}
        />
      </div>
      <h2 style={{ marginTop: 0, marginBottom: "8px" }}>Top Hunters by DPS Improvement</h2>
      <p style={{ color: "#9aa1b2", marginTop: 0, marginBottom: "20px" }}>
        Ranking hunters by their average % DPS improvement across monster &amp; star categories with more than one instance (&gt;1 hunt).
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {topData.top_hunters.map((hunter, rank) => {
          const positive = hunter.overall_pct_improvement >= 0;
          return (
            <div
              key={hunter.player_id}
              onClick={() => setScope([hunter.player_id])}
              style={{ background: "#1d2029", border: "1px solid #2c313e", borderRadius: "8px", padding: "20px", display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer", transition: "border-color 0.15s" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = "#e8b64c"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = "#2c313e"; }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: rank === 0 ? "#e8b64c" : rank === 1 ? "#abb2bf" : "#d19a66", minWidth: "32px", textAlign: "center" }}>
                  #{rank + 1}
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: "1.2rem", color: "#fff" }}>{hunter.player_name}</h3>
                  <p style={{ margin: "4px 0 0", color: "#9aa1b2", fontSize: "0.9rem" }}>
                    Qualifying categories: {hunter.qualifying_groups_count} monster/star groups (&gt;1 instance)
                  </p>
                </div>
              </div>

              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "1.8rem", fontWeight: "bold", color: positive ? "#58b368" : "#e06c75" }}>
                  {positive ? "+" : ""}{hunter.overall_pct_improvement}%
                </div>
                <div style={{ fontSize: "0.8rem", color: "#9aa1b2", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Avg DPS Growth
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
