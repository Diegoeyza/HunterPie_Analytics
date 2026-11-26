"use client";

import { useState } from "react";
import {CartesianGrid, ComposedChart, Line, Bar, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, } from "recharts";
import { ApiState, useApi } from "../../lib/useApi";
import SearchSelect from "../SearchSelect";
import { HunterSelect, MonsterSelect, StarsSelect, WeaponSelect, splitQuestValue, useQuestOptions } from "../FilterBar";
import { useFilterOptions } from "../useFilterOptions";
import EmptyState, { ScopeEmpty, scopeNames } from "../EmptyState";
import { GRID_STROKE, TICK, TIP_STYLE } from "../ChartKit";
import { fmtClearTime, fmtDps, fmtTime } from "../../lib/format";
import { useT, type TFn } from "@/lib/i18n";
import { monsterName, weaponTypeName } from "@/lib/names";

interface Point {
  hunt_id: number; started_at: string; monster: string; monster_id: number;
  quest_id: number | null; quest_stars: number | null; monster_max_hp: number | null;
  weapon: string; weapon_id: number | null; variant: string | null; player: string; dps: number;
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

function metricSpec(t: TFn): Record<ProgressMetric, {
  label: string; title: string; axis: string; note: string; unit: "%" | "s" | "";
}> {
  return {
    dps: {
      label: t("progress.metric.dps.label"),
      title: t("progress.metric.dps.title"),
      axis: t("progress.metric.dps.axis"),
      unit: "",
      note: t("progress.metric.dps.note"),
    },
    index: {
      label: t("progress.metric.index.label"),
      title: t("progress.metric.index.title"),
      axis: t("progress.metric.index.axis"),
      unit: "%",
      note: t("progress.metric.index.note"),
    },
    share: {
      label: t("progress.metric.share.label"),
      title: t("progress.metric.share.title"),
      axis: t("progress.metric.share.axis"),
      unit: "%",
      note: t("progress.metric.share.note"),
    },
    clear: {
      label: t("progress.metric.clear.label"),
      title: t("progress.metric.clear.title"),
      axis: t("progress.metric.clear.axis"),
      unit: "s",
      note: t("progress.metric.clear.note"),
    },
  };
}

export default function ProgressView({ scope, variantId, weaponName, clearScope, partySize, includeFailed }: { scope: number[]; variantId: number | string | null; weaponName: string | null; clearScope: () => void; partySize: number | null; includeFailed: boolean }) {
  const { t } = useT();
  const METRICS = metricSpec(t);
  const clearLabel = t("progress.series.clearTime");
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
        label={t("progress.filter.quest")}
        value={quest}
        options={questOptions}
        onChange={setQuest}
      />
      <StarsSelect value={stars} onChange={setStars} monster={monster} opts={opts} />
      <WeaponSelect value={weapon} onChange={setWeapon} opts={opts} />
      <HunterSelect value={player} onChange={setPlayer} opts={opts} />
      <label>{t("progress.filter.rollingWindow")}
        <input type="number" min={1} max={50} value={windowSize}
          onChange={(e) => setWindowSize(Number(e.target.value) || 5)} />
      </label>
      <label>{t("progress.filter.hunts")}
        <select value={huntLimit} onChange={(e) => setHuntLimit(e.target.value)}>
          <option value="50">{t("progress.filter.last50")}</option>
          <option value="100">{t("progress.filter.last100")}</option>
          <option value="200">{t("progress.filter.last200")}</option>
          <option value="all">{t("common.all")}</option>
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
          <p>{t("progress.empty.scope")}</p>
        </ScopeEmpty>
      );
    }
    return (
      <EmptyState what={t("progress.empty.none")}>
        <p>{t("progress.empty.import")} <code>python -m app.import_hunt --db hunts.db --file hunt.json</code></p>
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
      x: `#${p.hunt_id} ${monsterName(p.monster, p.monster_id)}${p.quest_stars ? ` ${p.quest_stars}★` : ""}`,
      value: round(value),
      avg: round(avg),
      clear_s: p.clear_s,
      player: p.player,
      weapon: p.variant ? `${weaponTypeName(p.weapon)} · ${p.variant}` : weaponTypeName(p.weapon),
    };
  });

  // 200+ hunts = 400+ SVG bar nodes; a line (single path) renders ~2x
  // faster and stays readable. Bars return under 60 points.
  const dense = rows.length > 60;

  return (
    <div className="card">
      {filters}
      <div className="filters">
        <span className="scope-label">{t("progress.measure")}</span>
        <div className="seg" role="group" aria-label={t("progress.measureAria")}>
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
      <h2>{t("progress.heading", { title: METRICS[metric].title, window: data.window })}</h2>
      <p className="blurb">{METRICS[metric].note}</p>
      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart data={rows}>
          <CartesianGrid stroke={GRID_STROKE} />
          <XAxis dataKey="x" tick={TICK} interval="preserveStartEnd" />
          <YAxis yAxisId="value" tick={TICK}
            tickFormatter={metric === "clear"
              ? (v: number) => fmtClearTime(v) : undefined}
            label={{ value: METRICS[metric].axis, fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, angle: -90, position: "insideLeft" }} />
          {metric !== "clear" && (
            <YAxis yAxisId="time" orientation="right" tick={TICK}
              tickFormatter={(v: number) => fmtClearTime(v)}
              label={{ value: clearLabel, fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, angle: 90, position: "insideRight" }} />
          )}
          <Tooltip contentStyle={TIP_STYLE} formatter={(value, name) => {
            const v = Number(value);
            // Durations read as m:ss everywhere; only this chart mixes one
            // with percentages, so pick by series name.
            if (String(name) === clearLabel || metric === "clear")
              return [fmtClearTime(v), name];
            const unit = METRICS[metric].unit;
            return [`${fmtDps(v)}${unit}`, name];
          }} />
          {dense ? (
            <Line yAxisId="value" type="monotone" dataKey="value"
              name={METRICS[metric].label}
              stroke="#e8b64c" dot={false} isAnimationActive={false} />
          ) : (
            <Bar yAxisId="value" dataKey="value" name={METRICS[metric].label}
              fill="#e8b64c" isAnimationActive={false} />
          )}
          <Line yAxisId="value" type="monotone" dataKey="avg" name={t("progress.series.avg")} stroke="#5aa9e6" dot={false} isAnimationActive={false} />
          {metric === "index" && (
            <ReferenceLine yAxisId="value" y={100} stroke="var(--muted)" strokeDasharray="4 4"
              label={{ value: t("progress.axis.usual"), fill: "var(--chart-tick, #9aa1b2)", fontSize: 10, position: "insideTopRight" }} />
          )}
          {metric !== "clear" && (
            <Line yAxisId="time" type="monotone" dataKey="clear_s" name={clearLabel} stroke="#58b368" dot={false} isAnimationActive={false} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
