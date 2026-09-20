"use client";

import { useMemo, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceArea,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { seriesColor, type HuntSummary } from "../../lib/api";
import { fmtDps, fmtInt, fmtPct, fmtTime } from "../../lib/format";
import { type Metric, computeDps, smoothDps, computeBurst } from "../../lib/metrics";
import { ApiState, useApi } from "../../lib/useApi";
import ChartTooltip from "../ChartTooltip";
import { TICK } from "../ChartKit";
import DataTable from "../DataTable";
import EmptyState from "../EmptyState";
import HunterCard from "../HunterCard";
import Modal from "../Modal";
import SearchSelect from "../SearchSelect";

interface CurvePoint { t: number; dmg: number; }
interface CurvePlayer { player: string; weapon: string | null; points: CurvePoint[]; }
interface CurveEvent { type: string; start: number; end: number | null; monster?: string | null; }
interface HuntCurve {
  hunt_id: number; monster: string; started_at: string;
  clear_s: number | null;
  quest: {
    quest_id: number | null; stars: number | null; max_hp: number | null;
  };
  players: CurvePlayer[]; events: CurveEvent[];
  hp_curve: { t: number; hp: number }[];
}

/** Active window for one hunter: own first→last damage snapshot, falling
 *  back to the hunt-wide first-hit→monster-death window, then to clear
 *  time. Mirrors _player_engagement_s/_engagement_duration_s in queries.py
 *  (curve downsampling keeps first/last points, so the windows match the
 *  backend's exactly) — DPS here is comparable with every other tab. */
function engagementOf(curve: HuntCurve, idx: number): number | null {
  const pts = curve.players[idx].points;
  const first = pts.length > 0 ? pts[0].t : null;
  const last = pts.length > 0 ? pts[pts.length - 1].t : null;
  if (first !== null && last !== null && last > first) return last - first;
  const firsts = curve.players
    .map((p) => (p.points.length > 0 ? p.points[0].t : null))
    .filter((t): t is number => t !== null);
  const lasts = curve.players
    .map((p) => (p.points.length > 0 ? p.points[p.points.length - 1].t : null))
    .filter((t): t is number => t !== null);
  const hFirst = firsts.length > 0 ? Math.min(...firsts) : null;
  const hLast = lasts.length > 0 ? Math.max(...lasts) : null;
  const death = curve.hp_curve.length > 0
    ? Math.max(...curve.hp_curve.map((s) => s.t)) : null;
  if (hFirst !== null && death !== null && death > hFirst) return death - hFirst;
  if (hFirst !== null && hLast !== null && hLast > hFirst) return hLast - hFirst;
  return curve.clear_s;
}

const columns: ColumnDef<HuntSummary>[] = [
  {
    id: "id", accessorKey: "id", header: "Hunt", meta: { cls: "num" },
    cell: ({ row }) => `#${row.original.id}`,
  },
  {
    id: "date", accessorKey: "started_at", header: "Date",
    cell: ({ row }) => row.original.started_at.slice(0, 16).replace("T", " "),
  },
  { id: "monster", accessorKey: "monster", header: "Monster" },
  {
    id: "quest", accessorFn: (r) => r.quest_id ?? -1, header: "Quest",
    cell: ({ row }) => (
      row.original.quest_id === null
        ? "—"
        : `#${row.original.quest_id}${row.original.quest_stars ? ` ${row.original.quest_stars}★` : ""}`
    ),
  },
  {
    id: "clear_s", accessorFn: (r) => r.clear_s ?? -1, header: "Clear",
    meta: { cls: "num" },
    cell: ({ row }) => fmtTime(row.original.clear_s),
  },
  {
    id: "players", accessorKey: "players", header: "Hunters",
    meta: { cls: "num" },
  },
  {
    id: "carts", accessorKey: "carts", header: "Carts",
    meta: { cls: "num" },
  },
  {
    id: "result", accessorFn: (r) => (r.cleared ? 1 : 0), header: "Result",
    cell: ({ row }) => (
      <span style={{ color: row.original.cleared ? "var(--good)" : "var(--bad)" }}>
        {row.original.cleared ? "Cleared" : "Failed"}
      </span>
    ),
  },
];

/** Detail popup for one hunt: summary stats, per-hunter damage + DPS cards,
 *  and the cumulative damage curve with enrage bands. Closes on backdrop
 *  click, the × button, or Escape. */
function HuntPopup({ hunt, onClose }: { hunt: HuntSummary; onClose: () => void }) {
  const [metric, setMetric] = useState<Metric>("damage");
  const { data } = useApi<HuntCurve>(`/hunts/${hunt.id}/curve`);
  // Keyed fetch: ignore a stale previous-hunt curve while the new one loads.
  const curve = data && data.hunt_id === hunt.id ? data : null;

  const members = useMemo(() => {
    if (!curve) return [];
    const team = curve.players.reduce(
      (s, p) => s + (p.points.length > 0 ? p.points[p.points.length - 1].dmg : 0), 0);
    return curve.players
      .map((p, i) => {
        const total = p.points.length > 0 ? p.points[p.points.length - 1].dmg : 0;
        const eng = engagementOf(curve, i);
        return {
          player: p.player, caption: p.weapon ?? "Unknown",
          total_damage: total,
          dps: eng ? total / eng : null,
          share: team > 0 ? total / team : 0, shareLabel: "of hunt",
        };
      })
      .sort((a, b) => b.total_damage - a.total_damage);
  }, [curve]);

  /** Merged time grid (player snapshot times + enrage boundaries, like
   *  CurveView's mergeSeries): one shared dataset so Lines render on the
   *  default axis and ReferenceAreas anchor exactly on band edges. */
  const chartData = useMemo(() => {
    if (!curve) return [];
    const enrages = curve.events.filter((e) => e.type === "enrage");

    // DPS death cutoff: last monster HP step (mirrors CurveView).
    // Keyed by player index (names are not guaranteed unique).
    const deathT = curve.hp_curve.length > 0
      ? Math.max(...curve.hp_curve.map((s) => s.t))
      : Infinity;
    const smoothed = new Map(
      curve.players.map((p, i) => [i, smoothDps(computeDps(p.points, deathT))]),
    );
    const burst = new Map(
      curve.players.map((p, i) => [i, computeBurst(p.points)]),
    );

    const times = [...new Set([
      0,
      ...curve.players.flatMap((p) => p.points.map((pt) => pt.t)),
      ...enrages.flatMap((e) => [e.start, e.end ?? curve.clear_s ?? 0]),
    ])].sort((a, b) => a - b);

    return times.map((t) => {
      const row: Record<string, number> = { t };
      curve.players.forEach((p, i) => {
        if (metric === "damage") {
          let v = 0;
          for (const pt of p.points) {
            if (pt.t <= t) v = pt.dmg;
            else break;
          }
          row[`p${i}`] = Math.round(v);
        } else {
          // Carry the last known value forward (like damage above): the
          // grid is the union of all hunters' timestamps, so exact-match
          // lookups leave every row with only one hunter defined and the
          // tooltip shows a single hunter. Before first point: no value.
          const series = metric === "burst"
            ? burst.get(i) ?? []
            : smoothed.get(i) ?? [];
          let v: number | null = null;
          for (const q of series) {
            if (q.t <= t + 1e-9) v = q.dps;
            else break;
          }
          if (v !== null) row[`p${i}`] = Math.round(v * 10) / 10;
        }
      });
      return row;
    });
  }, [curve, metric]);

  const title = `#${hunt.id} ${hunt.monster}`;
  const team = members.reduce((s, m) => s + m.total_damage, 0);
  const enrages = (curve?.events ?? []).filter((e) => e.type === "enrage");
  const stats: [string, string][] = [
    ["Date", hunt.started_at.slice(0, 10)],
    ["Quest", hunt.quest_id === null
      ? "—"
      : `#${hunt.quest_id}${hunt.quest_stars ? ` ${hunt.quest_stars}★` : ""}`],
    ["Result", hunt.cleared ? "Cleared" : "Failed"],
    ["Clear time", fmtTime(hunt.clear_s)],
    ["Carts", String(hunt.carts)],
    ["Team damage", team > 0 ? fmtInt(team) : "…"],
    ["Max HP", curve?.quest.max_hp ? fmtInt(curve.quest.max_hp) : "…"],
    ["Enrages", curve ? String(enrages.length) : "…"],
  ];

  return (
    <Modal label={title} onClose={onClose}>
      <div className="modal-head">
        <h2>{title}</h2>
        <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>
      <div className="modal-body">
          <div className="quest-stats">
            {stats.map(([label, value]) => (
              <div className="quest-stat" key={label}>
                <span className="muted">{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          {curve === null ? (
            <p>Loading hunt…</p>
          ) : (
            <>
              <div className="member-grid">
                {members.map((m, i) => (
                  <HunterCard key={m.player} m={m} mvp={i === 0 && members.length > 1} />
                ))}
              </div>
              <h3 className="chart-title">
                {metric === "damage"
                  ? "Cumulative damage"
                  : metric === "burst" ? "Instantaneous DPS" : "DPS"}
              </h3>
              <div className="filters">
                <label>Metric
                  <select
                    value={metric}
                    onChange={(e) => setMetric(e.target.value as Metric)}
                  >
                    <option value="damage">Cumulative damage</option>
                    <option value="dps">DPS (5s rolling avg)</option>
                    <option value="burst">Instantaneous DPS (5s window)</option>
                  </select>
                </label>
              </div>
              <div style={{ width: "100%", height: 260 }}>
                <ResponsiveContainer>
                  <LineChart data={chartData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                    <XAxis
                      dataKey="t" minTickGap={40}
                      tickFormatter={(v: number) => `${Math.round(v)}s`}
                      tick={TICK} stroke="var(--chart-tick, #9aa1b2)"
                    />
                    <YAxis
                      tickFormatter={(v: number) => (metric === "damage" && v >= 1000
                        ? `${Math.round(v / 100) / 10}k` : metric === "damage" ? `${v}` : `${Math.round(v * 10) / 10}`)}
                      tick={TICK} stroke="var(--chart-tick, #9aa1b2)" width={48}
                    />
                    <Tooltip
                      content={<ChartTooltip metric={metric} events={enrages} colorOf={() => "var(--bad, #e05c5c)"} />}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {enrages.map((e, i) => (
                      <ReferenceArea
                        key={i} x1={e.start} x2={e.end ?? undefined}
                        fill="var(--bad, #e05c5c)" fillOpacity={0.14} strokeDasharray="3 3"
                      />
                    ))}
                    {curve.players.map((p, i) => (
                      <Line
                        key={`${p.player}-${i}`} type="monotone" dataKey={`p${i}`} name={p.player}
                        stroke={seriesColor(i)} strokeWidth={2} dot={false}
                        isAnimationActive={false} connectNulls
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <p className="blurb">Red bands: enrage windows. DPS uses engagement time (own first→last hit), same as Damage curves tab.</p>
            </>
          )}
        </div>
    </Modal>
  );
}

export default function HuntsView({ scope, partySize }: { scope: number[]; partySize: number | null }) {
  const [monsterFilter, setMonsterFilter] = useState<string>("");
  const [resultFilter, setResultFilter] = useState<"" | "cleared" | "failed">("");
  const [selected, setSelected] = useState<HuntSummary | null>(null);

  const { data, error, loading } = useApi<{ hunts: HuntSummary[] }>("/hunts", {
    limit: 500,
    ...(scope.length > 0 && { player_ids: scope.join(",") }),
    ...(partySize != null && { players: partySize }),
  });
  const hunts = data?.hunts ?? null;

  const monsters = useMemo(
    () => [...new Set((hunts ?? []).map((h) => h.monster))].sort(),
    [hunts]
  );
  const filtered = useMemo(() => {
    let out = hunts ?? [];
    if (monsterFilter) out = out.filter((h) => h.monster === monsterFilter);
    if (resultFilter === "cleared") out = out.filter((h) => h.cleared);
    if (resultFilter === "failed") out = out.filter((h) => !h.cleared);
    return out;
  }, [hunts, monsterFilter, resultFilter]);

  if (error || loading || !hunts) return <ApiState error={error} loading={loading} />;
  if (hunts.length === 0) {
    return (
      <EmptyState what="hunts">
        <p>Import hunts with the button above — they land here.</p>
      </EmptyState>
    );
  }

  return (
    <div className="card">
      <h2>Hunts ({filtered.length}) — every run, latest first. Click a row for party stats and the damage curve.</h2>
      <div className="filters">
        <SearchSelect
          label="Monster"
          value={monsterFilter}
          showAll
          options={monsters.map((m) => ({ value: m, label: m }))}
          onChange={setMonsterFilter}
        />
        <div className="seg" role="group" aria-label="Result filter">
          <button type="button" className={resultFilter === "" ? "on" : ""}
            aria-pressed={resultFilter === ""}
            onClick={() => setResultFilter("")}>All</button>
          <button type="button" className={resultFilter === "cleared" ? "on" : ""}
            aria-pressed={resultFilter === "cleared"}
            onClick={() => setResultFilter("cleared")}>Cleared</button>
          <button type="button" className={resultFilter === "failed" ? "on" : ""}
            aria-pressed={resultFilter === "failed"}
            onClick={() => setResultFilter("failed")}>Failed</button>
        </div>
      </div>
      <DataTable
        data={filtered}
        columns={columns}
        initialSort={[{ id: "id", desc: true }]}
        getRowId={(r) => String(r.id)}
        onRowClick={setSelected}
        isSelected={(r) => r.id === selected?.id}
      />
      {selected && <HuntPopup hunt={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
