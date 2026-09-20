"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceArea,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { apiGet, apiGetCached, seriesColor, type FilterOptions, type HuntSummary } from "../../lib/api";
import SearchSelect from "../SearchSelect";
import EmptyState from "../EmptyState";
import ChartTooltip from "../ChartTooltip";

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
  const [hunts, setHunts] = useState<HuntSummary[] | null>(null);
  const [questKey, setQuestKey] = useState<string | null>(null);
  const [huntId, setHuntId] = useState<number | null>(null);
  const [curve, setCurve] = useState<CurveData | null>(null);
  const [showHp, setShowHp] = useState(true);
  const [metric, setMetric] = useState<Metric>("damage");
  const [nameToId, setNameToId] = useState<Map<string, number>>(new Map());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGetCached<FilterOptions>("/filter-options")
      .then((d) => setNameToId(new Map(d.players.map((p) => [p.name, p.id]))))
      .catch(() => {});
  }, []);

  // Quest list follows the hunter scope (any-of): only hunts the scoped
  // hunter(s) fought in. Refetches when the scope changes; a selection
  // that vanishes from the filtered list falls back to the latest quest.
  const scopeKey = scope.join(",");
  useEffect(() => {
    setHunts(null);
    setCurve(null);
    const params: Record<string, string | number> = { limit: 200 };
    if (scope.length > 0) params.player_ids = scopeKey;
    if (partySize != null) params.players = partySize;
    apiGet<{ hunts: HuntSummary[] }>("/hunts", params)
      .then((d) => {
        setHunts(d.hunts);
        if (d.hunts.length > 0) {
          // Hunts sharing a quest_id collapse into one entry: default to
          // the latest quest, showing All monsters. Starless quests group
          // per session (see keyOf below).
          const h0 = d.hunts[0];
          const key = h0.quest_id != null && h0.quest_stars != null ? `q:${h0.quest_id}`
            : h0.quest_id != null ? `s:${h0.quest_id}:${h0.started_at}`
            : `t:${h0.started_at}`;
          setQuestKey(key);
          setHuntId(null);
        } else {
          setQuestKey(null);
          setHuntId(null);
        }
      })
      .catch((e: Error) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scopeKey, partySize]);

  /** Quests in hunt-list order (latest first), grouped by quest_id so
   *  repeat runs of the same quest (e.g. #558) collapse into one entry.
   *  Unknown-star slots (e.g. field surveys) reuse ids across targets AND
   *  across sessions, so those group per session (quest id + start time):
   *  each entry is one real hunt with its true monster set. Hunts without
   *  a quest id stay per-session. */
  const quests = useMemo(() => {
    const groups = new Map<string, HuntSummary[]>();
    const keyOf = (h: HuntSummary) =>
      h.quest_id != null && h.quest_stars != null ? `q:${h.quest_id}`
      : h.quest_id != null ? `s:${h.quest_id}:${h.started_at}`
      : `t:${h.started_at}`;
    for (const h of hunts ?? []) {
      const key = keyOf(h);
      const g = groups.get(key);
      if (g) g.push(h);
      else groups.set(key, [h]);
    }
    return [...groups.entries()].map(([key, hs]) => {
      const qid = hs[0].quest_id;
      const stars = hs[0].quest_stars;
      const monsters = [...new Set(hs.map((h) => h.monster))].join(" + ");
      const when = `${hs[0].started_at.slice(0, 10)} ${hs[0].started_at.slice(11, 16)}`;
      const label = qid != null && stars != null
        ? `#${qid} ${stars}★ · ${monsters} · ${hs.length} hunt${hs.length === 1 ? "" : "s"}`
        : qid != null
          ? `#${qid} · ${when} · ${monsters}`
          : `${when} · ${monsters} · ${hs[0].players}p`;
      return { key, hunts: hs, label };
    });
  }, [hunts]);
  const questHunts = useMemo(
    () => quests.find((q) => q.key === questKey)?.hunts ?? hunts ?? [],
    [quests, questKey, hunts]
  );

  /** Null huntId = All monsters. Snapshots are quest-wide (identical across
   *  siblings), so one fetch carries the whole quest: players + every
   *  monster's HP and enrage spans. Display filters down when one monster
   *  is picked. */
  const fetchId = huntId ?? questHunts[0]?.id ?? null;
  useEffect(() => {
    if (fetchId == null) return;
    apiGet<CurveData>(`/hunts/${fetchId}/curve`, { quest_hp: 1 })
      .then(setCurve)
      .catch((e: Error) => setError(e.message));
  }, [fetchId]);

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
    if (huntId == null) return colored;
    return [...colored].sort((a, b) =>
      (a.hunt_id === huntId ? -1 : b.hunt_id === huntId ? 1 : a.hunt_id - b.hunt_id));
  }, [curve, huntId]);

  /** Monster filter: null = All. Narrow HP lines + enrage spans to the
   *  picked hunt; hunt_id match first, monster-name fallback for old data. */
  const visibleHp = useMemo(
    () => (huntId == null ? hpSeries : hpSeries.filter((s) => s.hunt_id === huntId)),
    [hpSeries, huntId]
  );
  const visibleEvents = useMemo(() => {
    if (!curve) return [];
    if (huntId == null) return curve.events;
    return curve.events.filter((e) =>
      e.hunt_id != null ? e.hunt_id === huntId : (e.monster ?? curve.monster) ===
        (hpSeries.find((s) => s.hunt_id === huntId)?.monster ?? curve.monster));
  }, [curve, huntId, hpSeries]);

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
      return "#e05c5c";
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

  const selectQuest = (key: string) => {
    setQuestKey(key);
    setHuntId(null);
  };

  if (error) return <p className="error">{error} — is the API running on :8000?</p>;
  if (!hunts) return <p>Loading…</p>;
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
          label="Quest"
          value={questKey ?? ""}
          options={quests.map((q) => ({ value: q.key, label: q.label }))}
          onChange={selectQuest}
        />
        <SearchSelect
          label="Monster"
          value={huntId === null ? "" : String(huntId)}
          placeholder="All monsters — type to search"
          options={questHunts.map((h) => ({
            value: String(h.id),
            label: `#${h.id} ${h.monster}${h.quest_stars ? ` ${h.quest_stars}★` : ""} · ${h.started_at.slice(0, 10)} · ${h.players}p`,
          }))}
          onChange={(v) => setHuntId(v ? Number(v) : null)}
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
            {huntId == null
              ? (visibleHp.length > 0
                  ? visibleHp.map((s) => `#${s.hunt_id} ${s.monster}`).join(" + ")
                  : `#${curve.hunt_id} ${curve.monster}`)
              : `#${curve.hunt_id} ${curve.monster}`}
            {curve.quest.stars ? ` · ${curve.quest.stars}★` : ""}
            {curve.quest.quest_id ? ` · quest #${curve.quest.quest_id}` : ""}
            {huntId != null && curve.quest.max_hp ? ` · ${Math.round(curve.quest.max_hp).toLocaleString()} HP` : ""}
            {curve.clear_s ? ` · cleared in ${Math.round(curve.clear_s)}s` : ""}
          </h2>
          {enrageGroups.length > 0 && (
            <div style={{ display: "flex", gap: 14, flexWrap: "wrap", margin: "4px 0 8px", fontSize: 12 }}>
              {enrageGroups.map((g) => (
                <span key={g.monster} style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "#9aa1b2" }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: g.color, opacity: 0.85, display: "inline-block" }} />
                  <span>
                    <strong style={{ color: "#c8cddd", fontWeight: 600 }}>{g.monster}</strong>
                    {" enraged "}
                    {g.spans.map((e) => `${Math.round(e.start)}s–${e.end != null ? `${Math.round(e.end)}s` : "…"}`).join(", ")}
                  </span>
                </span>
              ))}
            </div>
          )}
          <ResponsiveContainer width="100%" height={360}>
            <LineChart data={merged}>
              <CartesianGrid stroke="#2c313e" />
              <XAxis dataKey="t" tick={{ fill: "#9aa1b2", fontSize: 11 }}
                tickFormatter={(v: number) => `${Math.round(v)}s`}
                label={{ value: "time since quest start", fill: "#9aa1b2", fontSize: 11, position: "insideBottom", offset: -2 }} />
              <YAxis tick={{ fill: "#9aa1b2", fontSize: 11 }}
                label={{
                  value: metric === "damage" ? "cumulative damage" : metric === "burst" ? "DPS (5s window)" : "DPS (5s rolling avg)",
                  fill: "#9aa1b2", fontSize: 11, angle: -90, position: "insideLeft",
                }} />
              <YAxis yAxisId="hp" orientation="right" domain={[0, 1]}
                tick={{ fill: "#e05c5c", fontSize: 11 }}
                tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                label={{ value: "monster HP", fill: "#e05c5c", fontSize: 11, angle: 90, position: "insideRight" }}
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
