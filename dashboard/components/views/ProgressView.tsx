"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid, ComposedChart, Line, Bar, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { apiGet, type FilterOptions } from "../../lib/api";
import EmptyState from "../EmptyState";

interface Point {
  hunt_id: number; started_at: string; monster: string;
  quest_id: number | null; quest_stars: number | null; monster_max_hp: number | null;
  weapon: string; player: string; dps: number;
  clear_s: number | null; cleared: boolean;
}
interface ProgressData { points: Point[]; rolling: { hunt_id: number; avg_dps: number }[]; window: number; }

export default function ProgressView({ scope }: { scope: number[] }) {
  const [opts, setOpts] = useState<FilterOptions | null>(null);
  const [monster, setMonster] = useState("");
  const [weapon, setWeapon] = useState("");
  const [player, setPlayer] = useState("");
  const [quest, setQuest] = useState("");
  const [stars, setStars] = useState("");
  const [windowSize, setWindowSize] = useState(5);
  const [data, setData] = useState<ProgressData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<FilterOptions>("/filter-options").then(setOpts).catch(() => {});
  }, []);

  useEffect(() => {
    setError(null);
    apiGet<ProgressData>("/progress", {
      ...(monster && { monster_id: Number(monster) }),
      ...(weapon && { weapon_id: Number(weapon) }),
      ...(player && { player_id: Number(player) }),
      ...(quest && { quest_id: Number(quest) }),
      ...(stars && { stars: Number(stars) }),
      ...(scope.length > 0 && { player_ids: scope.join(",") }),
      window: windowSize,
    }).then(setData).catch((e: Error) => setError(e.message));
  }, [monster, weapon, player, quest, stars, windowSize, scope.join(",")]);

  if (error) return <p className="error">{error} — is the API running on :8000?</p>;
  if (!data) return <p>Loading…</p>;
  if (data.points.length === 0) {
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
    weapon: p.weapon,
  }));

  return (
    <div className="card">
      <div className="filters">
        <label>Monster
          <select value={monster} onChange={(e) => setMonster(e.target.value)}>
            <option value="">All</option>
            {opts?.monsters.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </label>
        <label>Quest
          <select value={quest} onChange={(e) => setQuest(e.target.value)}>
            <option value="">All</option>
            {opts?.quests.map((q) => (
              <option key={`${q.quest_id}-${q.stars}`} value={q.quest_id ?? ""}>
                #{q.quest_id} {q.monster}{q.stars ? ` ${q.stars}★` : ""}
              </option>
            ))}
          </select>
        </label>
        <label>Stars
          <select value={stars} onChange={(e) => setStars(e.target.value)}>
            <option value="">All</option>
            {opts?.stars.map((s) => <option key={s} value={s}>{s}★</option>)}
          </select>
        </label>
        <label>Weapon
          <select value={weapon} onChange={(e) => setWeapon(e.target.value)}>
            <option value="">All</option>
            {opts?.weapons.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
        </label>
        <label>Hunter
          <select value={player} onChange={(e) => setPlayer(e.target.value)}>
            <option value="">All</option>
            {opts?.players.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
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
          <YAxis yAxisId="dps" tick={{ fill: "#9aa1b2", fontSize: 11 }} />
          <YAxis yAxisId="time" orientation="right" tick={{ fill: "#9aa1b2", fontSize: 11 }} />
          <Tooltip contentStyle={{ background: "#1d2029", border: "1px solid #2c313e" }} />
          <Bar yAxisId="dps" dataKey="dps" name="DPS" fill="#e8b64c" />
          <Line yAxisId="dps" type="monotone" dataKey="avg" name="rolling avg" stroke="#5aa9e6" dot={false} />
          <Line yAxisId="time" type="monotone" dataKey="clear_s" name="clear (s)" stroke="#58b368" dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
