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

/** Merge n players' cumulative series + monster HP onto one time grid.
 *  Everything is forward-filled per row so all lines share the same x
 *  positions (a <Line> with its own `data` would be plotted by INDEX,
 *  misaligning shorter series like the 19-point HP curve). */
function mergeSeries(players: CurvePlayer[], hp: { t: number; hp: number }[]) {
  const times = Array.from(
    new Set([
      ...players.flatMap((p) => p.points.map((q) => q.t)),
      ...hp.map((q) => q.t),
    ])
  ).sort((a, b) => a - b);
  const hpSorted = [...hp].sort((a, b) => a.t - b.t);
  return times.map((t) => {
    const row: Record<string, number> = { t };
    for (const p of players) {
      let v: number | null = null;
      for (const q of p.points) {
        if (q.t <= t + 1e-9) v = q.dmg;
        else break;
      }
      if (v !== null) row[p.player] = Math.round(v);
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
    () => (curve ? mergeSeries(curve.players, showHp ? curve.hp_curve : []) : []),
    [curve, showHp]
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
                label={{ value: "cumulative damage", fill: "#9aa1b2", fontSize: 11, angle: -90, position: "insideLeft" }} />
              <YAxis yAxisId="hp" orientation="right" domain={[0, 1]}
                tick={{ fill: "#e05c5c", fontSize: 11 }}
                tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                label={{ value: "monster HP", fill: "#e05c5c", fontSize: 11, angle: 90, position: "insideRight" }}
                hide={!showHp} />
              <Tooltip
                contentStyle={{ background: "#1d2029", border: "1px solid #2c313e" }}
                labelFormatter={(v: number) => `${typeof v === "number" ? v.toFixed(1) : v}s`}
                formatter={(value, name) =>
                  name === "monster HP"
                    ? [`${((value as number) * 100).toFixed(1)}%`, name]
                    : [typeof value === "number" ? Math.round(value).toLocaleString() : value, name]
                }
              />
              <Legend />
              {curve.events.map((e, i) => (
                <ReferenceArea key={i} x1={e.start} x2={e.end ?? undefined}
                  fill="#e05c5c" fillOpacity={0.12}
                  label={{ value: e.type, fill: "#e05c5c", fontSize: 11, position: "insideTopRight" }} />
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
