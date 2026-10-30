"use client";

import { useState } from "react";
import {CartesianGrid, ComposedChart, Line, Bar, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, } from "recharts";
import { ApiState, useApi } from "../../lib/useApi";
import SearchSelect from "../SearchSelect";
import { HunterSelect, MonsterSelect, StarsSelect, WeaponSelect, splitQuestValue, useQuestOptions } from "../FilterBar";
import { useFilterOptions } from "../useFilterOptions";
import EmptyState, { ScopeEmpty, scopeNames } from "../EmptyState";
import { GRID_STROKE, TICK, TIP_STYLE } from "../ChartKit";
import { fmtTime } from "../../lib/format";

interface Point {
  hunt_id: number; started_at: string; monster: string;
  quest_id: number | null; quest_stars: number | null; monster_max_hp: number | null;
  weapon: string; variant: string | null; player: string; dps: number;
  share: number; index: number;
  clear_s: number | null; cleared: boolean;
}
interface Rolling {
  hunt_id: number; avg_dps: number;
  avg_share: number | null; avg_index: number | null; avg_clear: number | null;
}
interface ProgressData { points: Point[]; rolling: Rolling[]; window: number; }

/** Ways to read "progress". Raw DPS swings with the monster, the party and the
 *  clear speed; the two relative measures hold those still. */
type ProgressMetric = "dps" | "index" | "share" | "clear";

const METRICS: Record<ProgressMetric, {
  label: string; title: string; axis: string; note: string; unit: "%" | "s" | "";
}> = {
  dps: {
    label: "DPS", title: "DPS per hunt", axis: "DPS", unit: "",
    note: "Raw damage per second over your active window — sensitive to which monster you fought and how long the fight lasted.",
  },
  index: {
    label: "vs usual", title: "DPS vs your usual on that monster",
    axis: "% of usual", unit: "%",
    note: "100% = your median DPS on the same monster across these hunts, so switching to a harder or easier fight stops reading as a slump or a spike.",
  },
  share: {
    label: "Damage share", title: "Damage share per hunt",
    axis: "% of party", unit: "%",
    note: "Your part of the party's total damage — roughly flat when the whole party (or the monster's HP) changes, so it tracks your relative contribution.",
  },
  clear: {
    label: "Clear time", title: "Clear time per hunt", axis: "clear time",
    unit: "s", note: "Finish time per quest (m:ss) — lower is better; mixes in damage, routing and monster uptime.",
  },
};

export default function ProgressView({ scope, variantId, weaponName, clearScope, partySize, includeFailed }: { scope: number[]; variantId: number | string | null; weaponName: string | null; clearScope: () => void; partySize: number | null; includeFailed: boolean }) {
  const opts = useFilterOptions();
  const [monster, setMonster] = useState("");
  const [weapon, setWeapon] = useState("");
  const [player, setPlayer] = useState("");
  const [quest, setQuest] = useState("");
  const [stars, setStars] = useState("");
  const [windowSize, setWindowSize] = useState(5);
  const [huntLimit, setHuntLimit] = useState("100");
  const [metric, setMetric] = useState<ProgressMetric>("dps");

  // Survey quest values carry the target (`391@m10`); an explicit
  // monster pick by the user takes precedence over the suffix.
  const [qid, qmid] = splitQuestValue(quest);
  const { data, error, loading } = useApi<ProgressData>("/progress", {
    ...((monster || qmid) && { monster_id: Number(monster || qmid) }),
    ...(weapon && { weapon_id: Number(weapon) }),
    ...(weaponName && { weapon_name: weaponName }),
    ...(player && { player_id: Number(player) }),
    ...(qid && { quest_id: Number(qid) }),
    ...(stars && { stars: Number(stars) }),
    ...(scope.length > 0 && { player_ids: scope.join(",") }),
    ...(variantId !== null && { variant_id: variantId }),
    ...(huntLimit !== "all" && { limit: Number(huntLimit) }),
    ...(partySize != null && { players: partySize }),
    ...(includeFailed && { include_failed: true }),
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
  const rows = data.points.map((p, i) => {
    const roll = data.rolling[i];
    const value = metric === "index" ? p.index * 100
      : metric === "share" ? p.share * 100
        : metric === "clear" ? p.clear_s
          : p.dps;
    const avg = metric === "index"
      ? (roll?.avg_index != null ? roll.avg_index * 100 : null)
      : metric === "share"
        ? (roll?.avg_share != null ? roll.avg_share * 100 : null)
        : metric === "clear"
          ? roll?.avg_clear ?? null
          : roll?.avg_dps ?? null;
    const round = (v: number | null) => (v == null ? null : Math.round(v * 10) / 10);
    return {
      x: `#${p.hunt_id} ${p.monster}${p.quest_stars ? ` ${p.quest_stars}★` : ""}`,
      value: round(value),
      avg: round(avg),
      clear_s: p.clear_s ? Math.round(p.clear_s) : null,
      player: p.player,
      weapon: p.variant ? `${p.weapon} · ${p.variant}` : p.weapon,
    };
  });

  // 200+ hunts = 400+ SVG bar nodes; a line (single path) renders ~2x
  // faster and stays readable. Bars return under 60 points.
  const dense = rows.length > 60;

  return (
    <div className="card">
      {filters}
      <div className="filters">
        <span className="scope-label">Measure</span>
        <div className="seg" role="group" aria-label="Progress measure">
          {(Object.keys(METRICS) as ProgressMetric[]).map((m) => (
            <button
              key={m} type="button"
              className={metric === m ? "on" : ""}
              aria-pressed={metric === m}
              onClick={() => setMetric(m)}
            >
              {METRICS[m].label}
            </button>
          ))}
        </div>
      </div>
      <h2>{METRICS[metric].title} + {data.window}-hunt rolling average</h2>
      <p className="blurb">{METRICS[metric].note}</p>
      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart data={rows}>
          <CartesianGrid stroke={GRID_STROKE} />
          <XAxis dataKey="x" tick={TICK} interval="preserveStartEnd" />
          <YAxis yAxisId="value" tick={TICK}
            tickFormatter={metric === "clear"
              ? (v: number) => fmtTime(v) : undefined}
            label={{ value: METRICS[metric].axis, fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, angle: -90, position: "insideLeft" }} />
          {metric !== "clear" && (
            <YAxis yAxisId="time" orientation="right" tick={TICK}
              tickFormatter={(v: number) => fmtTime(v)}
              label={{ value: "clear time", fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, angle: 90, position: "insideRight" }} />
          )}
          <Tooltip contentStyle={TIP_STYLE} formatter={(value, name) => {
            const v = Number(value);
            // Durations read as m:ss everywhere; only this chart mixes one
            // with percentages, so pick by series name.
            if (String(name) === "clear time" || metric === "clear")
              return [fmtTime(v), name];
            const unit = METRICS[metric].unit;
            return [`${Math.round(v * 10) / 10}${unit}`, name];
          }} />
          {dense ? (
            <Line yAxisId="value" type="monotone" dataKey="value"
              name={METRICS[metric].label}
              stroke="#e8b64c" dot={false} isAnimationActive={false} />
          ) : (
            <Bar yAxisId="value" dataKey="value" name={METRICS[metric].label}
              fill="#e8b64c" isAnimationActive={false} />
          )}
          <Line yAxisId="value" type="monotone" dataKey="avg" name="rolling avg" stroke="#5aa9e6" dot={false} isAnimationActive={false} />
          {metric === "index" && (
            <ReferenceLine yAxisId="value" y={100} stroke="var(--muted)" strokeDasharray="4 4"
              label={{ value: "usual", fill: "var(--chart-tick, #9aa1b2)", fontSize: 10, position: "insideTopRight" }} />
          )}
          {metric !== "clear" && (
            <Line yAxisId="time" type="monotone" dataKey="clear_s" name="clear time" stroke="#58b368" dot={false} isAnimationActive={false} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
