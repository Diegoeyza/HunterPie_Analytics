"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceArea,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { apiGet, apiGetCached, seriesColor, type FilterOptions, type HuntSummary } from "../../lib/api";
import SearchSelect from "../SearchSelect";
import EmptyState from "../EmptyState";

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

type Metric = "damage" | "dps" | "burst";
const SMOOTH_WINDOW = 5;

/** Compute DPS from cumulative damage, starting from each player's first hit
 *  and ending at monster death (last HP step). After death, DPS plateaus. */
function computeDps(points: CurvePoint[], deathT: number): { t: number; dps: number }[] {
  if (points.length === 0) return [];
  const firstHit = points[0].t;
  return points.map((q) => {
    if (q.t <= firstHit) return { t: q.t, dps: 0 };
    const end = Math.min(q.t, deathT);
    const window = end - firstHit;
    return { t: q.t, dps: window > 0 ? q.dmg / window : 0 };
  });
}

/** Rolling mean over a player's DPS series. */
function smoothDps(dpsSeries: { t: number; dps: number }[]): { t: number; dps: number }[] {
  return dpsSeries.map((q, i) => {
    const seg = dpsSeries.slice(Math.max(0, i - SMOOTH_WINDOW + 1), i + 1);
    return { t: q.t, dps: seg.reduce((a, b) => a + b.dps, 0) / seg.length };
  });
}

/** Compute instantaneous DPS over a 5-second window ending at each timestamp. */
function computeBurst(points: CurvePoint[]): { t: number; dps: number }[] {
  if (points.length === 0) return [];
  const WINDOW = 5;
  return points.map((q) => {
    const windowStart = q.t - WINDOW;
    let dmgAtStart = 0;
    for (const p of points) {
      if (p.t > windowStart + 1e-9) break;
      dmgAtStart = p.dmg;
    }
    return { t: q.t, dps: (q.dmg - dmgAtStart) / WINDOW };
  });
}

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
      } else if (metric === "burst") {
        const hit = (burst.get(p.player) ?? []).find((q) => Math.abs(q.t - t) < 1e-9);
        if (hit) row[p.player] = Math.round(hit.dps * 10) / 10;
      } else {
        const hit = (smoothed.get(p.player) ?? []).find((q) => Math.abs(q.t - t) < 1e-9);
        if (hit) row[p.player] = Math.round(hit.dps * 10) / 10;
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

interface TooltipEntry { name?: unknown; value?: unknown; color?: string; }

/** Chart hover card: per-player values (same formatting as before) plus
 *  badges for whichever monsters are enraged at the hovered time.
 *  Enrage bands themselves carry no text (they overlap); identity comes
 *  from the color key above the chart and these badges. */
function CurveTooltip({ active, payload, label, metric, events, colorOf }: {
  active?: boolean; payload?: TooltipEntry[]; label?: number | string;
  metric: Metric; events: CurveEvent[]; colorOf: (e: CurveEvent) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const t = typeof label === "number" ? label : Number(label);
  const enraged = new Map<string, string>();
  if (Number.isFinite(t)) {
    for (const e of events) {
      if (e.type !== "enrage") continue;
      if (t >= e.start - 1e-9 && (e.end == null || t <= e.end + 1e-9)) {
        const m = e.monster ?? "";
        if (m && !enraged.has(m)) enraged.set(m, colorOf(e));
      }
    }
  }
  const fmt = (p: TooltipEntry) => {
    const name = String(p.name ?? "");
    if (name.includes(" HP") && typeof p.value === "number")
      return `${(p.value * 100).toFixed(1)}%`;
    if (typeof p.value !== "number") return String(p.value ?? "");
    return metric === "damage"
      ? Math.round(p.value).toLocaleString()
      : `${p.value.toFixed(1)} DPS`;
  };
  return (
    <div style={{ background: "#1d2029", border: "1px solid #2c313e", padding: "8px 10px", fontSize: 12 }}>
      <div style={{ color: "#9aa1b2", marginBottom: 4 }}>
        {Number.isFinite(t) ? `${t.toFixed(1)}s` : ""}
      </div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color ?? "#c8cddd" }}>
          {String(p.name ?? "")}: {fmt(p)}
        </div>
      ))}
      {enraged.size > 0 && (
        <div style={{ marginTop: 6, paddingTop: 6, borderTop: "1px solid #2c313e", display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[...enraged.entries()].map(([m, c]) => (
            <span key={m} style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "#c8cddd" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: c, display: "inline-block" }} />
              {m} enraged
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CurveView({ scope }: { scope: number[] }) {
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
  }, [scopeKey]);

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
              <Tooltip content={<CurveTooltip metric={metric} events={visibleEvents} colorOf={eventColor} />} />
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
