"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceArea,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { seriesColor, type HuntSummary } from "../../lib/api";
import { fmtInt } from "../../lib/format";
import { ApiState, useApi } from "../../lib/useApi";
import SearchSelect from "../SearchSelect";
import EmptyState from "../EmptyState";
import ChartTooltip from "../ChartTooltip";
import { GRID_STROKE, TICK } from "../ChartKit";
import { useFilterOptions } from "../useFilterOptions";

interface CurvePoint { t: number; dmg: number; }
interface CurvePlayer { player: string; weapon: string | null; variant: string | null; points: CurvePoint[]; }
interface CurveEvent { type: string; start: number; end: number | null; monster?: string | null; hunt_id?: number | null; }
interface CurveQuest {
  quest_id: number | null; stars: number | null; level: number | null;
  max_hp: number | null; variant: number | null; crown: number | null;
}
interface CurveHpPoint { t: number; hp: number; }
interface CurveHpSeries { hunt_id: number; monster: string; points: CurveHpPoint[]; }
interface CurveData {
  hunt_id: number; monster: string; started_at: string;
  clear_s: number | null; quest: CurveQuest;
  players: CurvePlayer[]; events: CurveEvent[];
  hp_curve: CurveHpPoint[];
  quest_hp?: CurveHpSeries[];
}

import { type Metric, computeDps, smoothDps, computeBurst } from "../../lib/metrics";

/** Merge n players' series + one HP series per visible monster onto one time
 *  grid. The DPS death cutoff is the last HP point across all visible
 *  series (single-monster view: that monster's death; All view: the last
 *  monster to die, since damage is quest-wide). Event boundary times
 *  (enrage start/end) are injected so that Recharts <ReferenceArea> has
 *  exact x-values to anchor to. */
function mergeSeries(players: CurvePlayer[], hpSeries: { key: string; points: { t: number; hp: number }[] }[],
                      events: CurveEvent[], metric: Metric) {
  const lasts = hpSeries.map((s) => s.points.length > 0 ? s.points[s.points.length - 1].t : -Infinity);
  const deathT = lasts.length > 0 ? Math.max(...lasts) : Infinity;
  const smoothed = new Map(
    players.map((p) => [p.player, smoothDps(computeDps(p.points, deathT))])
  );
  const burst = new Map(
    players.map((p) => [p.player, computeBurst(p.points)])
  );
  const eventTimes = events.flatMap((e) => [e.start, e.end ?? []]).flat();
  const times = Array.from(
    new Set([
      ...players.flatMap((p) => p.points.map((q) => q.t)),
      ...hpSeries.flatMap((s) => s.points.map((q) => q.t)),
      ...eventTimes,
    ])
  ).sort((a, b) => a - b);
  const hpSorted = hpSeries.map((s) => ({
    key: s.key, points: [...s.points].sort((a, b) => a.t - b.t),
  }));
  return times.map((t) => {
    const row: Record<string, number> = { t };
    for (const p of players) {
      if (metric === "damage") {
        let v: number | null = null;
        for (const q of p.points) {
          if (q.t <= t + 1e-9) v = q.dmg;
          else break;
        }
        if (v !== null) row[p.player] = Math.round(v);
      } else {
        // Carry the last known value forward (like damage above): the grid
        // is the union of all hunters' timestamps, so exact-match lookups
        // leave every row with only one hunter defined and the tooltip
        // shows a single hunter. Before a hunter's first point: no value.
        const series = metric === "burst"
          ? burst.get(p.player) ?? []
          : smoothed.get(p.player) ?? [];
        let v: number | null = null;
        for (const q of series) {
          if (q.t <= t + 1e-9) v = q.dps;
          else break;
        }
        if (v !== null) row[p.player] = Math.round(v * 10) / 10;
      }
    }
    for (const q of hpSorted) {
      let v: number | null = null;
      for (const p of q.points) {
        if (p.t <= t + 1e-9) v = p.hp;
        else break;
      }
      if (v !== null) row[q.key] = v;
    }
    return row;
  });
}

const HP_COLORS = ["#e05c5c", "#ef8354", "#c94f7c", "#e8b64c"];



export default function CurveView({ scope, partySize }: { scope: number[]; partySize: number | null }) {
  const opts = useFilterOptions();
  const [huntId, setHuntId] = useState<number | null>(null);
  const [monsterHunt, setMonsterHunt] = useState<number | null>(null);
  const [showHp, setShowHp] = useState(true);
  const [metric, setMetric] = useState<Metric>("damage");

  const nameToId = useMemo(
    () => new Map((opts?.players ?? []).map((p) => [p.name, p.id])),
    [opts]);

  // Hunt list follows the hunter scope (any-of): only hunts the scoped
  // hunter(s) fought in. A selection that vanishes from the filtered
  // list falls back to the latest hunt.
  const huntsQ = useApi<{ hunts: HuntSummary[] }>("/hunts", {
    limit: 200,
    ...(scope.length > 0 && { player_ids: scope.join(",") }),
    ...(partySize != null && { players: partySize }),
  });
  const hunts = huntsQ.data?.hunts ?? null;

  // Default to the latest hunt when the list loads or the selection
  // vanishes from a rescoped list.
  useEffect(() => {
    if (!hunts) return;
    if (hunts.length === 0) {
      if (huntId !== null) { setHuntId(null); setMonsterHunt(null); }
      return;
    }
    if (huntId === null || !hunts.some((h) => h.id === huntId)) {
      setHuntId(hunts[0].id);
      setMonsterHunt(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hunts]);

  /** One fetch per hunt. Snapshots are quest-wide (identical across
   *  siblings), so one fetch carries the whole quest instance: players +
   *  every monster's HP and enrage spans. Display filters down when one
   *  monster is picked. */
  const fetchId = huntId ?? hunts?.[0]?.id ?? null;
  const curveQ = useApi<CurveData>(
    fetchId === null ? "" : `/hunts/${fetchId}/curve`,
    fetchId === null ? null : { quest_hp: 1 });
  // Keyed fetch: ignore a stale previous-hunt curve while the new one loads.
  const curve = curveQ.data && curveQ.data.hunt_id === fetchId ? curveQ.data : null;
  const error = huntsQ.error ?? curveQ.error;

  /** Sibling monsters of this quest instance (one row per monster). */
  const siblingOptions = useMemo(() => {
    if (!curve) return [];
    const base = curve.quest_hp && curve.quest_hp.length > 0
      ? curve.quest_hp
      : [{ hunt_id: curve.hunt_id, monster: curve.monster }];
    return base.map((s) => ({
      value: String(s.hunt_id),
      label: `#${s.hunt_id} ${s.monster}`,
    }));
  }, [curve]);

  /** HP series for every monster in the quest (any number). Colors follow
   *  quest order so each monster keeps its shade whether viewed alone or
   *  all together. Keys carry hunt_id so duplicate monster names can't
   *  collide. Single-monster view sorts the selected hunt first. */
  const hpSeries = useMemo(() => {
    if (!curve) return [];
    const base = curve.quest_hp && curve.quest_hp.length > 0
      ? [...curve.quest_hp].sort((a, b) => a.hunt_id - b.hunt_id)
      : [{ hunt_id: curve.hunt_id, monster: curve.monster, points: curve.hp_curve }];
    const counts = new Map<string, number>();
    for (const s of base) counts.set(s.monster, (counts.get(s.monster) ?? 0) + 1);
    const colored = base.map((s, i) => ({
      hunt_id: s.hunt_id,
      monster: s.monster,
      key: `hp_${s.hunt_id}`,
      label: (counts.get(s.monster) ?? 1) > 1 ? `${s.monster} HP (#${s.hunt_id})` : `${s.monster} HP`,
      color: HP_COLORS[i % HP_COLORS.length],
      points: s.points,
    }));
    if (monsterHunt == null) return colored;
    return [...colored].sort((a, b) =>
      (a.hunt_id === monsterHunt ? -1 : b.hunt_id === monsterHunt ? 1 : a.hunt_id - b.hunt_id));
  }, [curve, monsterHunt]);

  /** Monster filter: null = All. Narrow HP lines + enrage spans to the
   *  picked sibling hunt; hunt_id match first, monster-name fallback for
   *  old data. */
  const visibleHp = useMemo(
    () => (monsterHunt == null ? hpSeries : hpSeries.filter((s) => s.hunt_id === monsterHunt)),
    [hpSeries, monsterHunt]
  );
  const visibleEvents = useMemo(() => {
    if (!curve) return [];
    if (monsterHunt == null) return curve.events;
    return curve.events.filter((e) =>
      e.hunt_id != null ? e.hunt_id === monsterHunt : (e.monster ?? curve.monster) ===
        (hpSeries.find((s) => s.hunt_id === monsterHunt)?.monster ?? curve.monster));
  }, [curve, monsterHunt, hpSeries]);

  /** Enrage shade per monster, matching its HP line; overlaps stack opacity. */
  const eventColor = useMemo(() => {
    const byHunt = new Map<number, string>();
    const byMonster = new Map<string, string>();
    for (const s of hpSeries) {
      byHunt.set(s.hunt_id, s.color);
      if (!byMonster.has(s.monster)) byMonster.set(s.monster, s.color);
    }
    return (e: CurveEvent) => {
      if (e.hunt_id != null && byHunt.has(e.hunt_id)) return byHunt.get(e.hunt_id)!;
      if (e.monster && byMonster.has(e.monster)) return byMonster.get(e.monster)!;
      return "var(--bad, #e05c5c)";
    };
  }, [hpSeries]);

  /** Per-monster enrage key (visible monsters): color swatch matching the
   *  monster's HP line plus its enrage spans. This replaces in-band text,
   *  which overlaps when spans collide. */
  const enrageGroups = useMemo(() => {
    if (!curve) return [];
    const groups = new Map<string, { monster: string; color: string; spans: CurveEvent[] }>();
    for (const e of visibleEvents) {
      if (e.type !== "enrage") continue;
      const m = e.monster ?? curve.monster;
      const g = groups.get(m);
      if (g) g.spans.push(e);
      else groups.set(m, { monster: m, color: eventColor(e), spans: [e] });
    }
    return [...groups.values()];
  }, [curve, visibleEvents, eventColor]);

  const merged = useMemo(
    () => (curve ? mergeSeries(curve.players, showHp ? visibleHp : [], visibleEvents, metric) : []),
    [curve, visibleHp, visibleEvents, showHp, metric]
  );

  const selectHunt = (v: string) => {
    setHuntId(v ? Number(v) : null);
    setMonsterHunt(null);
  };

  if (error) return <ApiState error={error} loading={false} />;
  if (huntsQ.loading || !hunts) return <p>Loading…</p>;
  if (hunts.length === 0) {
    return (
      <EmptyState what="hunts">
        <p>Import one with <code>python -m app.import_hunt --db hunts.db --file hunt.json</code></p>
      </EmptyState>
    );
  }

  return (
    <div className="card">
      <div className="filters">
        <SearchSelect
          label="Hunt"
          value={huntId === null ? "" : String(huntId)}
          options={(hunts ?? []).map((h) => ({
            value: String(h.id),
            label: `#${h.id} ${h.monster}${h.quest_stars ? ` ${h.quest_stars}★` : ""} · ${h.started_at.slice(0, 10)} · ${h.players}p${h.quest_id != null ? ` · quest #${h.quest_id}` : ""}`,
          }))}
          onChange={selectHunt}
        />
        <SearchSelect
          label="Monster"
          value={monsterHunt === null ? "" : String(monsterHunt)}
          placeholder="All monsters — type to search"
          options={siblingOptions}
          onChange={(v) => setMonsterHunt(v ? Number(v) : null)}
        />
        <label>
          <input type="checkbox" checked={showHp} onChange={(e) => setShowHp(e.target.checked)} />
          Monster HP
        </label>
        <label>Metric
          <select value={metric} onChange={(e) => setMetric(e.target.value as Metric)}>
            <option value="damage">Cumulative damage</option>
            <option value="dps">DPS (5s rolling avg)</option>
            <option value="burst">Instantaneous DPS (5s window)</option>
          </select>
        </label>
      </div>
      {curve && (
        <>
          <h2>
            {monsterHunt == null
              ? (visibleHp.length > 0
                  ? visibleHp.map((s) => `#${s.hunt_id} ${s.monster}`).join(" + ")
                  : `#${curve.hunt_id} ${curve.monster}`)
              : `#${curve.hunt_id} ${curve.monster}`}
            {curve.quest.stars ? ` · ${curve.quest.stars}★` : ""}
            {curve.quest.quest_id ? ` · quest #${curve.quest.quest_id}` : ""}
            {monsterHunt != null && curve.quest.max_hp ? ` · ${fmtInt(curve.quest.max_hp)} HP` : ""}
            {curve.clear_s ? ` · cleared in ${Math.round(curve.clear_s)}s` : ""}
          </h2>
          {enrageGroups.length > 0 && (
            <div style={{ display: "flex", gap: 14, flexWrap: "wrap", margin: "4px 0 8px", fontSize: 12 }}>
              {enrageGroups.map((g) => (
                <span key={g.monster} style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--chart-tick, #9aa1b2)" }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: g.color, opacity: 0.85, display: "inline-block" }} />
                  <span>
                    <strong style={{ color: "var(--text, #c8cddd)", fontWeight: 600 }}>{g.monster}</strong>
                    {" enraged "}
                    {g.spans.map((e) => `${Math.round(e.start)}s–${e.end != null ? `${Math.round(e.end)}s` : "…"}`).join(", ")}
                  </span>
                </span>
              ))}
            </div>
          )}
          <ResponsiveContainer width="100%" height={360}>
            <LineChart data={merged}>
              <CartesianGrid stroke={GRID_STROKE} />
              <XAxis dataKey="t" tick={TICK}
                tickFormatter={(v: number) => `${Math.round(v)}s`}
                label={{ value: "time since quest start", fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, position: "insideBottom", offset: -2 }} />
              <YAxis tick={TICK}
                label={{
                  value: metric === "damage" ? "cumulative damage" : metric === "burst" ? "DPS (5s window)" : "DPS (5s rolling avg)",
                  fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, angle: -90, position: "insideLeft",
                }} />
              <YAxis yAxisId="hp" orientation="right" domain={[0, 1]}
                tick={{ fill: "var(--bad, #e05c5c)", fontSize: 11 }}
                tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                label={{ value: "monster HP", fill: "var(--bad, #e05c5c)", fontSize: 11, angle: 90, position: "insideRight" }}
                hide={!showHp} />
              <Tooltip content={<ChartTooltip metric={metric} events={visibleEvents} colorOf={eventColor} />} />
              <Legend />
              {visibleEvents.map((e, i) => {
                const c = eventColor(e);
                return (
                  <ReferenceArea key={e.hunt_id != null ? `${e.hunt_id}-${e.start}-${i}` : i}
                    x1={e.start} x2={e.end ?? undefined}
                    fill={c} fillOpacity={0.18}
                    stroke={c} strokeOpacity={0.4} strokeDasharray="3 3" />
                );
              })}
              {curve.players.map((p, i) => {
                const dimmed = scope.length > 0 &&
                  !scope.includes(nameToId.get(p.player) ?? -1);
                return (
                  <Line key={p.player} type="monotone" dataKey={p.player}
                    name={`${p.player}${p.weapon ? ` (${p.weapon}${p.variant ? ` · ${p.variant}` : ""})` : ""}`}
                    stroke={seriesColor(i)} dot={false} strokeWidth={dimmed ? 1 : 2}
                    strokeOpacity={dimmed ? 0.25 : 1} connectNulls />
                );
              })}
              {showHp && visibleHp.map((s) => (
                <Line key={s.key} type="monotone" dataKey={s.key}
                  yAxisId="hp" name={s.label} stroke={s.color}
                  strokeDasharray="6 3" dot={false} strokeWidth={1.5} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}
