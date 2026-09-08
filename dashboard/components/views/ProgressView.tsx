"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid, ComposedChart, Line, Bar, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { apiGet } from "../../lib/api";
import SearchSelect from "../SearchSelect";
import { useFilterOptions } from "../useFilterOptions";
import EmptyState, { ScopeEmpty, scopeNames } from "../EmptyState";

interface Point {
  hunt_id: number; started_at: string; monster: string;
  quest_id: number | null; quest_stars: number | null; monster_max_hp: number | null;
  weapon: string; variant: string | null; player: string; dps: number;
  clear_s: number | null; cleared: boolean;
}
interface ProgressData { points: Point[]; rolling: { hunt_id: number; avg_dps: number }[]; window: number; }

export default function ProgressView({ scope, variantId, clearScope }: { scope: number[]; variantId: number | null; clearScope: () => void }) {
  const opts = useFilterOptions();
  const [monster, setMonster] = useState("");
  const [weapon, setWeapon] = useState("");
  const [player, setPlayer] = useState("");
  const [quest, setQuest] = useState("");
  const [stars, setStars] = useState("");
  const [windowSize, setWindowSize] = useState(5);
  const [data, setData] = useState<ProgressData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    // Survey quest values carry the target (`391@m10`); an explicit
    // monster pick by the user takes precedence over the suffix.
    const [qid, qmid] = quest.includes("@m") ? quest.split("@m") : [quest, ""];
    apiGet<ProgressData>("/progress", {
      ...((monster || qmid) && { monster_id: Number(monster || qmid) }),
      ...(weapon && { weapon_id: Number(weapon) }),
      ...(player && { player_id: Number(player) }),
      ...(qid && { quest_id: Number(qid) }),
      ...(stars && { stars: Number(stars) }),
      ...(scope.length > 0 && { player_ids: scope.join(",") }),
      ...(variantId !== null && { variant_id: variantId }),
      window: windowSize,
    }).then(setData).catch((e: Error) => setError(e.message));
  }, [monster, weapon, player, quest, stars, windowSize, scope.join(","), variantId]);

  // One option per quest group: real quests collapse multi-monster runs
  // into one entry, while unknown-star slots (field surveys) stay split
  // by target — keyed by both so unrelated hunts never merge. Survey
  // values carry the target monster (`391@m10`) so the filter below can
  // narrow to it; real quests filter by quest_id alone.
  const questOptions = useMemo(() => {
    const byId = new Map<string, { id: number; mid: number; monsters: string[]; stars: number | null }>();
    for (const q of opts?.quests ?? []) {
      if (q.quest_id == null) continue;
      const key = `${q.quest_id}|${q.monster}`;
      const g = byId.get(key);
      if (g) {
        if (!g.monsters.includes(q.monster)) g.monsters.push(q.monster);
      } else {
        byId.set(key, { id: q.quest_id, mid: q.monster_id, monsters: [q.monster], stars: q.stars });
      }
    }
    return [...byId.values()].map((g) => ({
      value: g.stars != null ? String(g.id) : `${g.id}@m${g.mid}`,
      label: `#${g.id} ${g.monsters.join(" + ")}${g.stars ? ` ${g.stars}★` : ""}`,
    }));
  }, [opts]);

  if (error) return <p className="error">{error} — is the API running on :8000?</p>;
  if (!data) return <p>Loading…</p>;
  if (data.points.length === 0) {
    if (scope.length > 0) {
      return (
        <ScopeEmpty names={scopeNames(scope, opts?.players)} onClear={clearScope}>
          <p>They aren't in these hunts — pick something they joined.</p>
        </ScopeEmpty>
      );
    }
    return (
      <EmptyState what="hunts match these filters">
        <p>Import one with <code>python -m app.import_hunt --db hunts.db --file hunt.json</code></p>
      </EmptyState>
    );
  }

  // rolling[i] aligns with points[i] (same order, one row per hunt-player)
  const rows = data.points.map((p, i) => ({
    x: `#${p.hunt_id} ${p.monster}${p.quest_stars ? ` ${p.quest_stars}★` : ""}`,
    dps: Math.round(p.dps * 10) / 10,
    avg: Math.round((data.rolling[i]?.avg_dps ?? 0) * 10) / 10,
    clear_s: p.clear_s ? Math.round(p.clear_s) : null,
    player: p.player,
    weapon: p.variant ? `${p.weapon} · ${p.variant}` : p.weapon,
  }));

  return (
    <div className="card">
      <div className="filters">
        <SearchSelect
          label="Monster"
          value={monster}
          options={(opts?.monsters ?? []).map((m) => ({ value: String(m.id), label: m.name }))}
          onChange={(v) => { setMonster(v); setStars(""); }}
        />
        <SearchSelect
          label="Quest"
          value={quest}
          options={questOptions}
          onChange={setQuest}
        />
        <label>Stars
          <select value={stars} onChange={(e) => setStars(e.target.value)}>
            <option value="">All</option>
            {(monster ? (opts?.monster_stars[Number(monster)] ?? opts?.stars ?? []) : opts?.stars ?? []).map((s) => <option key={s} value={s}>{s}★</option>)}
          </select>
        </label>
        <SearchSelect
          label="Weapon"
          value={weapon}
          options={(opts?.weapons ?? []).map((w) => ({ value: String(w.id), label: w.name }))}
          onChange={setWeapon}
        />
        <SearchSelect
          label="Hunter"
          value={player}
          options={(opts?.players ?? []).map((p) => ({ value: String(p.id), label: p.name }))}
          onChange={setPlayer}
        />
        <label>Rolling window
          <input type="number" min={1} max={50} value={windowSize}
            onChange={(e) => setWindowSize(Number(e.target.value) || 5)} />
        </label>
      </div>
      <h2>DPS per hunt + {data.window}-hunt rolling average</h2>
      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart data={rows}>
          <CartesianGrid stroke="#2c313e" />
          <XAxis dataKey="x" tick={{ fill: "#9aa1b2", fontSize: 11 }} interval="preserveStartEnd" />
          <YAxis yAxisId="dps" tick={{ fill: "#9aa1b2", fontSize: 11 }}
            label={{ value: "DPS", fill: "#9aa1b2", fontSize: 11, angle: -90, position: "insideLeft" }} />
          <YAxis yAxisId="time" orientation="right" tick={{ fill: "#9aa1b2", fontSize: 11 }}
            label={{ value: "clear time (s)", fill: "#9aa1b2", fontSize: 11, angle: 90, position: "insideRight" }} />
          <Tooltip contentStyle={{ background: "#1d2029", border: "1px solid #2c313e" }} />
          <Bar yAxisId="dps" dataKey="dps" name="DPS" fill="#e8b64c" />
          <Line yAxisId="dps" type="monotone" dataKey="avg" name="rolling avg" stroke="#5aa9e6" dot={false} />
          <Line yAxisId="time" type="monotone" dataKey="clear_s" name="clear (s)" stroke="#58b368" dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
