"use client";

import { useState } from "react";
import {CartesianGrid, ComposedChart, Line, Bar, ResponsiveContainer, XAxis, YAxis, } from "recharts";
import { ApiState, useApi } from "../../lib/useApi";
import SearchSelect from "../SearchSelect";
import { HunterSelect, MonsterSelect, StarsSelect, WeaponSelect, splitQuestValue, useQuestOptions } from "../FilterBar";
import { useFilterOptions } from "../useFilterOptions";
import EmptyState, { ScopeEmpty, scopeNames } from "../EmptyState";
import { ChartTip, GRID_STROKE, TICK } from "../ChartKit";

interface Point {
  hunt_id: number; started_at: string; monster: string;
  quest_id: number | null; quest_stars: number | null; monster_max_hp: number | null;
  weapon: string; variant: string | null; player: string; dps: number;
  clear_s: number | null; cleared: boolean;
}
interface ProgressData { points: Point[]; rolling: { hunt_id: number; avg_dps: number }[]; window: number; }

export default function ProgressView({ scope, variantId, clearScope, partySize }: { scope: number[]; variantId: number | string | null; clearScope: () => void; partySize: number | null }) {
  const opts = useFilterOptions();
  const [monster, setMonster] = useState("");
  const [weapon, setWeapon] = useState("");
  const [player, setPlayer] = useState("");
  const [quest, setQuest] = useState("");
  const [stars, setStars] = useState("");
  const [windowSize, setWindowSize] = useState(5);
  const [huntLimit, setHuntLimit] = useState("100");

  // Survey quest values carry the target (`391@m10`); an explicit
  // monster pick by the user takes precedence over the suffix.
  const [qid, qmid] = splitQuestValue(quest);
  const { data, error, loading } = useApi<ProgressData>("/progress", {
    ...((monster || qmid) && { monster_id: Number(monster || qmid) }),
    ...(weapon && { weapon_id: Number(weapon) }),
    ...(player && { player_id: Number(player) }),
    ...(qid && { quest_id: Number(qid) }),
    ...(stars && { stars: Number(stars) }),
    ...(scope.length > 0 && { player_ids: scope.join(",") }),
    ...(variantId !== null && { variant_id: variantId }),
    ...(huntLimit !== "all" && { limit: Number(huntLimit) }),
    ...(partySize != null && { players: partySize }),
    window: windowSize,
  });

  // One option per quest group: real quests collapse multi-monster runs
  // into one entry, while unknown-star slots (field surveys) stay split
  // by target — keyed by both so unrelated hunts never merge.
  const questOptions = useQuestOptions(opts);

  const filters = (
    <div className="filters">
      <MonsterSelect value={monster} opts={opts}
        onChange={(v) => { setMonster(v); setStars(""); }} />
      <SearchSelect
        label="Quest"
        value={quest}
        options={questOptions}
        onChange={setQuest}
      />
      <StarsSelect value={stars} onChange={setStars} monster={monster} opts={opts} />
      <WeaponSelect value={weapon} onChange={setWeapon} opts={opts} />
      <HunterSelect value={player} onChange={setPlayer} opts={opts} />
      <label>Rolling window
        <input type="number" min={1} max={50} value={windowSize}
          onChange={(e) => setWindowSize(Number(e.target.value) || 5)} />
      </label>
      <label>Hunts
        <select value={huntLimit} onChange={(e) => setHuntLimit(e.target.value)}>
          <option value="50">Last 50</option>
          <option value="100">Last 100</option>
          <option value="200">Last 200</option>
          <option value="all">All</option>
        </select>
      </label>
    </div>
  );

  if (error || loading || !data) {
    return (
      <div className="card">
        {filters}
        <ApiState error={error} loading={loading} />
      </div>
    );
  }
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

  // 200+ hunts = 400+ SVG bar nodes; a line (single path) renders ~2x
  // faster and stays readable. Bars return under 60 points.
  const dense = rows.length > 60;

  return (
    <div className="card">
      {filters}
      <h2>DPS per hunt + {data.window}-hunt rolling average</h2>
      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart data={rows}>
          <CartesianGrid stroke={GRID_STROKE} />
          <XAxis dataKey="x" tick={TICK} interval="preserveStartEnd" />
          <YAxis yAxisId="dps" tick={TICK}
            label={{ value: "DPS", fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, angle: -90, position: "insideLeft" }} />
          <YAxis yAxisId="time" orientation="right" tick={TICK}
            label={{ value: "clear time (s)", fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, angle: 90, position: "insideRight" }} />
          <ChartTip />
          {dense ? (
            <Line yAxisId="dps" type="monotone" dataKey="dps" name="DPS"
              stroke="#e8b64c" dot={false} isAnimationActive={false} />
          ) : (
            <Bar yAxisId="dps" dataKey="dps" name="DPS" fill="#e8b64c"
              isAnimationActive={false} />
          )}
          <Line yAxisId="dps" type="monotone" dataKey="avg" name="rolling avg" stroke="#5aa9e6" dot={false} isAnimationActive={false} />
          <Line yAxisId="time" type="monotone" dataKey="clear_s" name="clear (s)" stroke="#58b368" dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
