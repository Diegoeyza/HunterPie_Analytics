"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceArea,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { apiGet, seriesColor, type FilterOptions, type HuntSummary } from "../../lib/api";
import EmptyState from "../EmptyState";

interface CurvePoint { t: number; dmg: number; }
interface CurvePlayer { player: string; weapon: string | null; points: CurvePoint[]; }
interface CurveEvent { type: string; start: number; end: number | null; }
interface CurveQuest {
  quest_id: number | null; stars: number | null; level: number | null;
  max_hp: number | null; variant: number | null; crown: number | null;
}
interface CurveData {
  hunt_id: number; monster: string; started_at: string;
  clear_s: number | null; quest: CurveQuest;
  players: CurvePlayer[]; events: CurveEvent[];
  hp_curve: { t: number; hp: number }[];
}

type Metric = "damage" | "dps";
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

/** Merge n players' series + monster HP onto one time grid.
 *  Event boundary times (enrage start/end) are injected so that
 *  Recharts <ReferenceArea> has exact x-values to anchor to. */
function mergeSeries(players: CurvePlayer[], hp: { t: number; hp: number }[],
                     events: CurveEvent[], metric: Metric) {
  const deathT = hp.length > 0 ? hp[hp.length - 1].t : Infinity;
  const smoothed = new Map(
    players.map((p) => [p.player, smoothDps(computeDps(p.points, deathT))])
  );
  const eventTimes = events.flatMap((e) => [e.start, e.end ?? []]).flat();
  const times = Array.from(
    new Set([
      ...players.flatMap((p) => p.points.map((q) => q.t)),
      ...hp.map((q) => q.t),
      ...eventTimes,
    ])
  ).sort((a, b) => a - b);
  const hpSorted = [...hp].sort((a, b) => a.t - b.t);
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
        const hit = (smoothed.get(p.player) ?? []).find((q) => Math.abs(q.t - t) < 1e-9);
        if (hit) row[p.player] = Math.round(hit.dps * 10) / 10;
      }
    }
    let hv: number | null = null;
    for (const q of hpSorted) {
      if (q.t <= t + 1e-9) hv = q.hp;
      else break;
    }
    if (hv !== null) row["hp"] = hv;
    return row;
  });
}

export default function CurveView({ scope }: { scope: number[] }) {
  const [hunts, setHunts] = useState<HuntSummary[] | null>(null);
  const [huntId, setHuntId] = useState<number | null>(null);
  const [curve, setCurve] = useState<CurveData | null>(null);
  const [showHp, setShowHp] = useState(true);
  const [metric, setMetric] = useState<Metric>("damage");
  const [nameToId, setNameToId] = useState<Map<string, number>>(new Map());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<FilterOptions>("/filter-options")
      .then((d) => setNameToId(new Map(d.players.map((p) => [p.name, p.id]))))
      .catch(() => {});
  }, []);

  useEffect(() => {
    apiGet<{ hunts: HuntSummary[] }>("/hunts", { limit: 200 })
      .then((d) => {
        setHunts(d.hunts);
        if (d.hunts.length > 0) setHuntId(d.hunts[0].id);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    if (huntId === null) return;
    apiGet<CurveData>(`/hunts/${huntId}/curve`)
      .then(setCurve)
      .catch((e: Error) => setError(e.message));
  }, [huntId]);

  const merged = useMemo(
    () => (curve ? mergeSeries(curve.players, showHp ? curve.hp_curve : [], curve.events, metric) : []),
    [curve, showHp, metric]
  );

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
        <label>Hunt
          <select value={huntId ?? ""} onChange={(e) => setHuntId(Number(e.target.value))}>
            {hunts.map((h) => (
              <option key={h.id} value={h.id}>
                #{h.id} {h.monster} · {h.started_at.slice(0, 10)} · {h.players}p
              </option>
            ))}
          </select>
        </label>
        <label>
          <input type="checkbox" checked={showHp} onChange={(e) => setShowHp(e.target.checked)} />
          Monster HP
        </label>
        <label>Metric
          <select value={metric} onChange={(e) => setMetric(e.target.value as Metric)}>
            <option value="damage">Cumulative damage</option>
            <option value="dps">DPS (5s rolling avg)</option>
          </select>
        </label>
      </div>
      {curve && (
        <>
          <h2>
            #{curve.hunt_id} {curve.monster}
            {curve.quest.stars ? ` · ${curve.quest.stars}★` : ""}
            {curve.quest.quest_id ? ` · quest #${curve.quest.quest_id}` : ""}
            {curve.quest.max_hp ? ` · ${Math.round(curve.quest.max_hp).toLocaleString()} HP` : ""}
            {curve.clear_s ? ` · cleared in ${Math.round(curve.clear_s)}s` : ""}
          </h2>
          <ResponsiveContainer width="100%" height={360}>
            <LineChart data={merged}>
              <CartesianGrid stroke="#2c313e" />
              <XAxis dataKey="t" tick={{ fill: "#9aa1b2", fontSize: 11 }}
                tickFormatter={(v: number) => `${Math.round(v)}s`}
                label={{ value: "time since quest start", fill: "#9aa1b2", fontSize: 11, position: "insideBottom", offset: -2 }} />
              <YAxis tick={{ fill: "#9aa1b2", fontSize: 11 }}
                label={{
                  value: metric === "damage" ? "cumulative damage" : "DPS (5s rolling avg)",
                  fill: "#9aa1b2", fontSize: 11, angle: -90, position: "insideLeft",
                }} />
              <YAxis yAxisId="hp" orientation="right" domain={[0, 1]}
                tick={{ fill: "#e05c5c", fontSize: 11 }}
                tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                label={{ value: "monster HP", fill: "#e05c5c", fontSize: 11, angle: 90, position: "insideRight" }}
                hide={!showHp} />
              <Tooltip
                contentStyle={{ background: "#1d2029", border: "1px solid #2c313e" }}
                labelFormatter={(v) => `${typeof v === "number" ? v.toFixed(1) : v}s`}
                formatter={(value, name) => {
                  if (name === "monster HP") return [`${((value as number) * 100).toFixed(1)}%`, name];
                  if (typeof value !== "number") return [value, name];
                  return metric === "damage"
                    ? [Math.round(value).toLocaleString(), name]
                    : [`${value.toFixed(1)} DPS`, name];
                }}
              />
              <Legend />
              {curve.events.map((e, i) => (
                <ReferenceArea key={i} x1={e.start} x2={e.end ?? undefined}
                  fill="#e05c5c" fillOpacity={0.18}
                  stroke="#e05c5c" strokeOpacity={0.4} strokeDasharray="3 3" />
              ))}
              {curve.players.map((p, i) => {
                const dimmed = scope.length > 0 &&
                  !scope.includes(nameToId.get(p.player) ?? -1);
                return (
                  <Line key={p.player} type="monotone" dataKey={p.player}
                    name={`${p.player}${p.weapon ? ` (${p.weapon})` : ""}`}
                    stroke={seriesColor(i)} dot={false} strokeWidth={dimmed ? 1 : 2}
                    strokeOpacity={dimmed ? 0.25 : 1} connectNulls />
                );
              })}
              {showHp && curve.hp_curve.length > 0 && (
                <Line type="monotone" dataKey="hp"
                  yAxisId="hp" name="monster HP" stroke="#e05c5c"
                  strokeDasharray="6 3" dot={false} strokeWidth={1.5} connectNulls />
              )}
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}
