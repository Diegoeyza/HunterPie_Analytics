"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceArea,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { seriesColor, type HuntSummary } from "../../lib/api";
import { fmtInt, fmtPct, fmtTime } from "../../lib/format";
import { computeDps, smoothDps } from "../../lib/metrics";
import { ApiState, useApi } from "../../lib/useApi";
import SearchSelect from "../SearchSelect";
import EmptyState from "../EmptyState";
import ChartTooltip from "../ChartTooltip";
import { GRID_STROKE, TICK } from "../ChartKit";
import { useFilterOptions } from "../useFilterOptions";

interface DpsPoint { t: number; dmg: number; }
interface SurvivalCurvePlayer {
  player: string; weapon: string | null; weapon_name?: string | null;
  variant: string | null; points: DpsPoint[];
}
interface SurvivalHpPoint { t: number; hp: number; red?: number | null; max?: number | null; }
interface SurvivalHpPlayer { player: string; points: SurvivalHpPoint[]; }
interface SurvivalRow {
  player: string; min_hp: number | null; avg_hp: number | null;
  time_below_50: number; time_below_25: number; time_full: number;
  samples: number;
}
interface SurvivalEvent { type: string; start: number; end: number | null; monster?: string | null; hunt_id?: number | null; }
interface SurvivalData {
  hunt_id: number; monster: string; started_at: string;
  clear_s: number | null;
  quest: { quest_id: number | null; stars: number | null; max_hp: number | null };
  players: SurvivalCurvePlayer[]; events: SurvivalEvent[];
  hp_curve: { t: number; hp: number }[];
  player_hp: SurvivalHpPlayer[]; survival: SurvivalRow[];
  cleared?: boolean;
}

/** Merge per-player smoothed DPS + HP samples onto one time grid.
 *  Both carry forward (like Damage curves): the grid is the union of all
 *  timestamps, so exact-match lookups would strand every row with a
 *  single hunter defined. Monster HP merges the same way when enabled. */
function mergeSurvival(
  players: SurvivalCurvePlayer[],
  hpByPlayer: Map<string, SurvivalHpPoint[]>,
  monsterHp: { t: number; hp: number }[],
  events: SurvivalEvent[],
  deathT: number,
) {
  const smoothed = new Map(
    players.map((p) => [p.player, smoothDps(computeDps(p.points, deathT))])
  );
  const times = Array.from(
    new Set([
      ...players.flatMap((p) => p.points.map((q) => q.t)),
      ...[...hpByPlayer.values()].flatMap((pts) => pts.map((q) => q.t)),
      ...monsterHp.map((q) => q.t),
      ...events.flatMap((e) => [e.start, e.end ?? []]).flat(),
    ])
  ).sort((a, b) => a - b);
  return times.map((t) => {
    const row: Record<string, number> = { t };
    for (const p of players) {
      const series = smoothed.get(p.player) ?? [];
      let v: number | null = null;
      for (const q of series) {
        if (q.t <= t + 1e-9) v = q.dps;
        else break;
      }
      if (v !== null) row[`${p.player}__dps`] = Math.round(v * 10) / 10;
      const hpPts = hpByPlayer.get(p.player) ?? [];
      let h: number | null = null;
      for (const q of hpPts) {
        if (q.t <= t + 1e-9) h = q.hp;
        else break;
      }
      if (h !== null) row[`${p.player}__hp`] = h;
    }
    let m: number | null = null;
    for (const q of monsterHp) {
      if (q.t <= t + 1e-9) m = q.hp;
      else break;
    }
    if (m !== null) row.monster_hp = m;
    return row;
  });
}

export default function SurvivalView({ scope, partySize }: { scope: number[]; partySize: number | null }) {
  const opts = useFilterOptions();
  const [huntId, setHuntId] = useState<number | null>(null);
  const [showMonsterHp, setShowMonsterHp] = useState(false);
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const nameToId = useMemo(
    () => new Map((opts?.players ?? []).map((p) => [p.name, p.id])),
    [opts]);

  const huntsQ = useApi<{ hunts: HuntSummary[] }>("/hunts", {
    limit: 200,
    ...(scope.length > 0 && { player_ids: scope.join(",") }),
    ...(partySize != null && { players: partySize }),
  });
  const hunts = huntsQ.data?.hunts ?? null;

  const latestWithHealth = useMemo(
    () => hunts?.find((h) => h.has_health) ?? null,
    [hunts]);

  // Default to the latest hunt WITH hunter HP; fall back to latest hunt.
  useEffect(() => {
    if (!hunts) return;
    if (hunts.length === 0) {
      if (huntId !== null) setHuntId(null);
      return;
    }
    if (huntId === null || !hunts.some((h) => h.id === huntId)) {
      setHuntId((hunts.find((h) => h.has_health) ?? hunts[0]).id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hunts]);

  const fetchId = huntId ?? hunts?.[0]?.id ?? null;
  const curveQ = useApi<SurvivalData>(fetchId === null ? "" : `/hunts/${fetchId}/curve`);
  const curve = curveQ.data && curveQ.data.hunt_id === fetchId ? curveQ.data : null;
  const error = huntsQ.error ?? curveQ.error;

  const visiblePlayers = useMemo(
    () => (curve?.players ?? []).filter((p) => !hidden.has(p.player)),
    [curve, hidden]);
  const hpByPlayer = useMemo(() => {
    const m = new Map<string, SurvivalHpPoint[]>();
    for (const s of curve?.player_hp ?? []) {
      if (!hidden.has(s.player)) m.set(s.player, [...s.points].sort((a, b) => a.t - b.t));
    }
    return m;
  }, [curve, hidden]);

  const deathT = useMemo(() => {
    const lasts = [
      ...(curve?.hp_curve ?? []).map((s) => s.t),
      ...[...hpByPlayer.values()].flatMap((pts) => pts.map((q) => q.t)),
    ];
    return lasts.length > 0 ? Math.max(...lasts) : Infinity;
  }, [curve, hpByPlayer]);

  const merged = useMemo(
    () => (curve
      ? mergeSurvival(visiblePlayers, hpByPlayer,
          showMonsterHp ? [...curve.hp_curve].sort((a, b) => a.t - b.t) : [],
          curve.events, deathT)
      : []),
    [curve, visiblePlayers, hpByPlayer, showMonsterHp, deathT]);

  // A mod-only hunt has a single damage total (one point), not a curve:
  // DPS is companion data. Hide the DPS series/axis instead of drawing a
  // flat line at zero.
  // Remote hunters may be missing from the mod's party read: say so instead
  // of implying the party never took damage.
  const missingHp = useMemo(() => {
    if (!curve) return 0;
    const names = new Set(curve.player_hp.map((p) => p.player));
    return curve.players.filter((p) => !names.has(p.player)).length;
  }, [curve]);

  const hasDps = useMemo(
    () => (curve?.players ?? []).some((p) => p.points.length > 1),
    [curve]);

  const survivalRows = useMemo(() => {
    if (!curve) return [];
    const byPlayer = new Map(curve.survival.map((s) => [s.player, s]));
    return visiblePlayers.map((p) => ({ player: p.player, row: byPlayer.get(p.player) ?? null }));
  }, [curve, visiblePlayers]);

  const togglePlayer = (name: string) =>
    setHidden((s) => {
      const next = new Set(s);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });

  const selectHunt = (v: string) => setHuntId(v ? Number(v) : null);

  if (error) return <ApiState error={error} loading={false} />;
  if (huntsQ.loading || !hunts) return <p>Loading…</p>;
  if (hunts.length === 0) {
    return (
      <EmptyState what="hunts">
        <p>Import hunts first — survival data appears once dumps carry hunter HP.</p>
      </EmptyState>
    );
  }
  if (!latestWithHealth) {
    return (
      <div className="card">
        <h2>Survival — no hunter HP yet</h2>
        <p className="blurb">
          None of these hunts carry per-hunter HP. Enable <b>HuntDumper 0.11+</b>
          before a quest (it polls party HP once a second); reloading scripts
          mid-hunt skips that hunt. Older hunts keep their damage curves, but
          have no survival data.
        </p>
      </div>
    );
  }

  const selectedHasHealth = curve !== null && curve.player_hp.length > 0;

  return (
    <div className="card">
      <div className="filters">
        <SearchSelect
          label="Hunt"
          value={huntId === null ? "" : String(huntId)}
          options={(hunts ?? []).map((h) => ({
            value: String(h.id),
            label: `#${h.id} ${h.monster}${h.quest_stars ? ` ${h.quest_stars}★` : ""} · ${h.started_at.slice(0, 10)} · ${h.players}p${h.has_health ? " · HP" : ""}`,
          }))}
          onChange={selectHunt}
        />
        <label>
          <input type="checkbox" checked={showMonsterHp} onChange={(e) => setShowMonsterHp(e.target.checked)} />
          Monster HP
        </label>
      </div>
      {curve && (
        <>
          <h2>
            #{curve.hunt_id} {curve.monster}
            {curve.quest.stars ? ` · ${curve.quest.stars}★` : ""}
            {curve.clear_s
              ? ` · ${curve.cleared === false ? "failed after" : "cleared in"} ${Math.round(curve.clear_s)}s`
              : ""}
          </h2>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "4px 0 8px" }}>
            {curve.players.map((p, i) => {
              const off = hidden.has(p.player);
              const dimmed = scope.length > 0 &&
                !scope.includes(nameToId.get(p.player) ?? -1);
              return (
                <button
                  key={p.player}
                  type="button"
                  onClick={() => togglePlayer(p.player)}
                  aria-pressed={!off}
                  title={off ? `Show ${p.player}` : `Hide ${p.player}`}
                  style={{
                    display: "inline-flex", alignItems: "center", gap: 6,
                    opacity: off || dimmed ? 0.45 : 1,
                    border: "1px solid var(--chart-tick, #2c313e)",
                    borderRadius: 12, padding: "2px 10px", fontSize: 12,
                    background: "transparent", color: "var(--text, #c8cddd)",
                    cursor: "pointer",
                  }}
                >
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: seriesColor(i), display: "inline-block" }} />
                  {p.player}
                </button>
              );
            })}
          </div>
          {!selectedHasHealth ? (
            <p className="blurb">
              This hunt has no hunter HP (captured without HuntDumper 0.11+).{" "}
              {latestWithHealth && latestWithHealth.id !== huntId && (
                <button type="button" onClick={() => setHuntId(latestWithHealth.id)}>
                  Open the latest hunt with HP
                </button>
              )}
            </p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={360}>
                <LineChart data={merged}>
                  <CartesianGrid stroke={GRID_STROKE} />
                  <XAxis dataKey="t" tick={TICK} minTickGap={40}
                    tickFormatter={(v: number) => `${Math.round(v)}s`}
                    label={{ value: "time since quest start", fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, position: "insideBottom", offset: -2 }} />
                  {hasDps && (
                    <YAxis tick={TICK}
                      label={{ value: "DPS (5s rolling avg)", fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, angle: -90, position: "insideLeft" }} />
                  )}
                  <YAxis yAxisId="hp" orientation="right" domain={[0, 1]}
                    tick={{ fill: "var(--bad, #e05c5c)", fontSize: 11 }}
                    tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                    label={{ value: "hunter HP", fill: "var(--bad, #e05c5c)", fontSize: 11, angle: 90, position: "insideRight" }} />
                  <Tooltip content={<ChartTooltip metric="dps" events={curve.events} colorOf={() => "var(--bad, #e05c5c)"} />} />
                  <Legend />
                  {curve.events.map((e, i) => (
                    <ReferenceArea key={e.hunt_id != null ? `${e.hunt_id}-${e.start}-${i}` : i}
                      x1={e.start} x2={e.end ?? undefined}
                      fill="var(--bad, #e05c5c)" fillOpacity={0.12}
                      stroke="var(--bad, #e05c5c)" strokeOpacity={0.35} strokeDasharray="3 3" />
                  ))}
                  {visiblePlayers.map((p, i) => {
                    const idx = curve.players.findIndex((q) => q.player === p.player);
                    const c = seriesColor(idx >= 0 ? idx : i);
                    const dimmed = scope.length > 0 &&
                      !scope.includes(nameToId.get(p.player) ?? -1);
                    return [
                      <Line key={`${p.player}-hp`} type="monotone" dataKey={`${p.player}__hp`}
                        yAxisId="hp" name={`${p.player} HP`} stroke={c}
                        dot={false} strokeWidth={dimmed ? 1 : 2.5}
                        strokeOpacity={dimmed ? 0.3 : 1} connectNulls />,
                      hasDps && (
                        <Line key={`${p.player}-dps`} type="monotone" dataKey={`${p.player}__dps`}
                          name={`${p.player} DPS`} stroke={c}
                          strokeDasharray="3 3" dot={false} strokeWidth={1.25}
                          strokeOpacity={dimmed ? 0.2 : 0.7} connectNulls />
                      ),
                    ];
                  })}
                  {showMonsterHp && (
                    <Line type="monotone" dataKey="monster_hp"
                      yAxisId="hp" name={`${curve.monster} HP`} stroke="#e05c5c"
                      strokeDasharray="6 3" dot={false} strokeWidth={1.5} connectNulls />
                  )}
                </LineChart>
              </ResponsiveContainer>
              {missingHp > 0 && (
                <p className="blurb">
                  {missingHp === curve.players.length
                    ? "No hunter HP captured for this hunt."
                    : `${missingHp} hunter${missingHp === 1 ? "" : "s"} without HP data in this capture.`}
                </p>
              )}
              <h3 className="chart-title">Time in danger</h3>
              <div className="table-wrap">
                <table className="grid">
                  <thead>
                    <tr>
                      <th>Hunter</th>
                      <th className="num">Min HP</th>
                      <th className="num">Avg HP</th>
                      <th className="num">&lt; 50%</th>
                      <th className="num">&lt; 25%</th>
                      <th className="num">Full HP</th>
                      <th className="num">Samples</th>
                    </tr>
                  </thead>
                  <tbody>
                    {survivalRows.map(({ player, row }) => (
                      <tr key={player}>
                        <td>{player}</td>
                        <td className="num">{row?.min_hp != null ? fmtPct(row.min_hp) : "—"}</td>
                        <td className="num">{row?.avg_hp != null ? fmtPct(row.avg_hp) : "—"}</td>
                        <td className="num">{row ? fmtTime(row.time_below_50) : "—"}</td>
                        <td className="num">{row ? fmtTime(row.time_below_25) : "—"}</td>
                        <td className="num">{row ? fmtTime(row.time_full) : "—"}</td>
                        <td className="num">{row ? fmtInt(row.samples) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="blurb">
                Solid lines: hunter HP (right axis).
                {hasDps
                  ? " Dashed lines: DPS (left axis)."
                  : " No DPS for this hunt: the companion wasn\u2019t running, and only the companion records damage over time."}
                {" "}Averages and time-in-danger cap gaps at 2.5 s so loading
                screens don&apos;t count as danger. HP is sampled ~1 Hz by
                HuntDumper 0.11+.
              </p>
            </>
          )}
        </>
      )}
    </div>
  );
}
