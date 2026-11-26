"use client";

import { useMemo, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceArea,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { seriesColor, type AppSettings, type HuntSummary, type HuntHighlights } from "../../lib/api";
import { t as tr, useT } from "@/lib/i18n";
import { awardName, monsterName, weaponTypeName } from "@/lib/names";
import { fmtAward, fmtClearTime, fmtDateTime, fmtDps, fmtInt, fmtPct, fmtTime } from "../../lib/format";
import { type Metric, computeDps, smoothDps, computeBurst } from "../../lib/metrics";
import { ApiState, useApi } from "../../lib/useApi";
import ChartTooltip from "../ChartTooltip";
import { TICK } from "../ChartKit";
import Collapsible from "../Collapsible";
import DataTable from "../DataTable";
import EmptyState from "../EmptyState";
import HunterCard from "../HunterCard";
import Modal from "../Modal";
import SearchSelect from "../SearchSelect";

interface CurvePoint { t: number; dmg: number; }
interface CurvePlayer {
  player: string; weapon: string | null; weapon_name?: string | null;
  /** Hunter rank at quest time (mod); null for companion-only hunts. */
  hunter_rank?: number | null;
  points: CurvePoint[];
}
interface CurveEvent {
  type: string; start: number; end: number | null;
  monster?: string | null; monster_id?: number | null;
}
interface HuntCurve {
  hunt_id: number; monster: string; started_at: string;
  clear_s: number | null;
  quest: {
    quest_id: number | null; stars: number | null; max_hp: number | null;
  };
  players: CurvePlayer[]; events: CurveEvent[];
  hp_curve: { t: number; hp: number }[];
  survival?: { player: string; min_hp: number | null; avg_hp: number | null;
    time_below_50: number; time_below_25: number; time_full: number;
    samples: number }[];
}

/** Shared quest end: the party's last damage point (mirrors the backend's
 *  party-last snapshot max). The overlay divides each hunter's damage by
 *  (results - own first), so quest mode ends every window here. */
function partyLastT(curve: HuntCurve): number | null {
  const lasts = curve.players
    .map((p) => (p.points.length > 0 ? p.points[p.points.length - 1].t : null))
    .filter((t): t is number => t !== null);
  return lasts.length > 0 ? Math.max(...lasts) : null;
}

/** Active window for one hunter (mirrors the backend's engagement window
 *  functions; curve downsampling keeps first/last points, so the windows
 *  match the backend's exactly) — DPS here is comparable with every tab. */
/** First sample that actually carries damage: the curve may start with an
 *  anchoring (0, 0) point so cumulative charts begin at quest start, and
 *  that must not stretch the engagement window back over the run-up. */
function firstHitT(points: { t: number; dmg: number }[]): number | null {
  const hit = points.find((p) => p.dmg > 0);
  return hit ? hit.t : (points.length > 0 ? points[0].t : null);
}

function engagementOf(curve: HuntCurve, idx: number, questMode = false): number | null {
  const pts = curve.players[idx].points;
  const first = firstHitT(pts);
  const last = pts.length > 0 ? pts[pts.length - 1].t : null;
  if (questMode) {
    // Shared quest end from each hunter's own start (like the overlay).
    const end = partyLastT(curve);
    if (first !== null && end !== null && end > first) return end - first;
  }
  if (first !== null && last !== null && last > first) return last - first;
  const firsts = curve.players
    .map((p) => firstHitT(p.points))
    .filter((t): t is number => t !== null);
  const lasts = curve.players
    .map((p) => (p.points.length > 0 ? p.points[p.points.length - 1].t : null))
    .filter((t): t is number => t !== null);
  const hFirst = firsts.length > 0 ? Math.min(...firsts) : null;
  const hLast = lasts.length > 0 ? Math.max(...lasts) : null;
  if (hFirst !== null && hLast !== null && hLast > hFirst) return hLast - hFirst;
  return curve.clear_s;
}

const makeColumns = (t: typeof tr): ColumnDef<HuntSummary>[] => [
  {
    id: "id", accessorKey: "id", header: t("hunts.col.id"), meta: { cls: "num" },
    cell: ({ row }) => `#${row.original.id}`,
  },
  {
    id: "date", accessorKey: "started_at", header: t("hunts.col.date"),
    cell: ({ row }) => fmtDateTime(row.original.started_at),
  },
  {
    id: "monster", accessorKey: "monster", header: t("table.filter.monster"),
    cell: ({ row }) => monsterName(row.original.monster, row.original.monster_id),
  },
  {
    id: "quest", accessorFn: (r) => r.quest_id ?? -1, header: t("hunts.col.quest"),
    cell: ({ row }) => (
      row.original.quest_id === null
        ? "—"
        : `#${row.original.quest_id}${row.original.quest_stars ? ` ${row.original.quest_stars}★` : ""}`
    ),
  },
  {
    id: "clear_s", accessorFn: (r) => r.clear_s ?? -1, header: t("hunts.col.clear"),
    meta: { cls: "num" },
    cell: ({ row }) => fmtClearTime(row.original.clear_s),
  },
  {
    id: "players", accessorKey: "players", header: t("hunts.col.hunters"),
    meta: { cls: "num" },
    cell: ({ row }) => {
      const party = row.original.party ?? [];
      if (party.length === 0) return row.original.players;
      const tip = party.map((p) => p.hunter_rank != null
        ? `${p.player} · HR ${p.hunter_rank}`
        : p.player).join("\n");
      return <span title={tip}>{row.original.players}</span>;
    },
  },
  {
    id: "highlights", accessorFn: (r) => r.highlight_count ?? 0,
    header: t("hunts.col.highlights"), meta: { cls: "num" },
    cell: ({ row }) => {
      const n = row.original.highlight_count ?? 0;
      if (!n) return "—";
      const ids = row.original.highlight_award_ids ?? [];
      const names = row.original.highlight_names ?? [];
      const labels = names.map((name, i) => awardName(ids[i], name));
      return <span title={labels.join(", ")}>{n}</span>;
    },
  },
  {
    id: "carts", accessorKey: "carts", header: t("hunts.col.carts"),
    meta: { cls: "num" },
  },
  {
    id: "result", accessorFn: (r) => (r.cleared ? 1 : 0), header: t("hunts.col.result"),
    cell: ({ row }) => (
      <span style={{ color: row.original.cleared ? "var(--good)" : "var(--bad)" }}>
        {row.original.cleared ? t("hunts.cleared") : t("hunts.failed")}
      </span>
    ),
  },
];

/** Detail popup for one hunt: summary stats, per-hunter damage + DPS cards,
 *  and the cumulative damage curve with enrage bands. Closes on backdrop
 *  click, the × button, or Escape. */
function HuntPopup({ hunt, onClose }: { hunt: HuntSummary; onClose: () => void }) {
  const { t, locale } = useT();
  const [metric, setMetric] = useState<Metric>("damage");
  const { data } = useApi<HuntCurve>(`/hunts/${hunt.id}/curve`);
  // Keyed fetch: ignore a stale previous-hunt curve while the new one loads.
  const curve = data && data.hunt_id === hunt.id ? data : null;
  const hlQ = useApi<HuntHighlights>(`/hunts/${hunt.id}/highlights`);
  const highlights = hlQ.data && hlQ.data.hunt_id === hunt.id ? hlQ.data : null;
  const settingsQ = useApi<AppSettings>("/settings");
  const questMode = settingsQ.data?.dps_window === "quest";

  // Rank is stored per hunt/player. Missing on mod-only hunts and on dumps
  // from older companion builds, so every use is optional.
  const rankOf = useMemo(() => {
    const m = new Map<string, number>();
    for (const p of curve?.players ?? []) {
      if (p.hunter_rank != null) m.set(p.player, p.hunter_rank);
    }
    return m;
  }, [curve]);
  const rankTitle = (name: string, rank?: number | null) => {
    const r = rank ?? rankOf.get(name);
    return r != null ? `${name} · ${t("table.card.hunterRank", { rank: r })}` : name;
  };

  const members = useMemo(() => {
    if (!curve) return [];
    const team = curve.players.reduce(
      (s, p) => s + (p.points.length > 0 ? p.points[p.points.length - 1].dmg : 0), 0);
    // Quest mode ends every window at the party's last hit, from each
    // hunter's own start — the overlay divides each damage by
    // (results - own first), so early-stoppers dilute like in game.
    return curve.players
      .map((p, i) => {
        const pts = p.points;
        const total = pts.length > 0 ? pts[pts.length - 1].dmg : 0;
        const eng = engagementOf(curve, i, questMode);
        return {
          player: p.player,
          caption: p.weapon_name ?? (p.weapon ? weaponTypeName(p.weapon) : t("common.unknown")),
          hunter_rank: p.hunter_rank ?? null,
          total_damage: total,
          dps: eng ? total / eng : null,
          share: team > 0 ? total / team : 0, shareLabel: t("hunts.ofHunt"),
        };
      })
      .sort((a, b) => b.total_damage - a.total_damage);
  }, [curve, questMode, locale]);

  /** Merged time grid (player snapshot times + enrage boundaries, like
   *  CurveView's mergeSeries): one shared dataset so Lines render on the
   *  default axis and ReferenceAreas anchor exactly on band edges. */
  const chartData = useMemo(() => {
    if (!curve) return [];
    const enrages = curve.events.filter((e) => e.type === "enrage");

    // DPS quest end: the party's last hit (mirrors CurveView). The curve
    // decays to the same final DPS the headlines show.
    // Keyed by player index (names are not guaranteed unique).
    const endT = partyLastT(curve) ?? Infinity;
    const smoothed = new Map(
      curve.players.map((p, i) => [i, smoothDps(computeDps(p.points, endT))]),
    );

    const times = [...new Set([
      0,
      ...curve.players.flatMap((p) => p.points.map((pt) => pt.t)),
      ...enrages.flatMap((e) => [e.start, e.end ?? curve.clear_s ?? 0]),
    ])].sort((a, b) => a - b);
    // Burst windows are evaluated on the shared grid so a 5s-sampled party
    // member is not treated as if every sample were a 1s frame.
    const burst = new Map(
      curve.players.map((p, i) => [
        i,
        computeBurst(p.points, metric === "burst1" ? 1 : 5, times),
      ]),
    );

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
          const series = metric === "burst" || metric === "burst1"
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

  const title = `#${hunt.id} ${monsterName(hunt.monster, hunt.monster_id)}`;
  const team = members.reduce((s, m) => s + m.total_damage, 0);
  const enrages = (curve?.events ?? []).filter((e) => e.type === "enrage");
  const stats: [string, string][] = [
    [t("hunts.col.date"), fmtDateTime(hunt.started_at)],
    [t("hunts.col.quest"), hunt.quest_id === null
      ? "—"
      : `#${hunt.quest_id}${hunt.quest_stars ? ` ${hunt.quest_stars}★` : ""}`],
    [t("hunts.col.result"), hunt.cleared ? t("hunts.cleared") : t("hunts.failed")],
    [t("hunts.stat.clearTime"), fmtClearTime(hunt.clear_s)],
    [t("hunts.col.carts"), String(hunt.carts)],
    [t("hunts.stat.teamDamage"), team > 0 ? fmtInt(team) : "…"],
    [t("hunts.stat.maxHp"), curve?.quest.max_hp ? fmtInt(curve.quest.max_hp) : "…"],
    [t("hunts.stat.enrages"), curve ? String(enrages.length) : "…"],
  ];

  return (
    <Modal label={title} onClose={onClose}>
      <div className="modal-head">
        <h2>{title}</h2>
        <button type="button" className="modal-close" onClick={onClose} aria-label={t("common.close")}>
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
            <p>{t("hunts.loadingCurve")}</p>
          ) : (
            <>
              <div className="member-grid">
                {members.map((m, i) => (
                  <HunterCard key={m.player} m={m} mvp={i === 0 && members.length > 1} />
                ))}
              </div>
              <Collapsible
                title={t("hunts.damageChart")}
                subtitle={metric === "damage"
                  ? t("curves.metric.damage")
                  : metric === "burst" ? t("hunts.chart.sub.burst")
                  : metric === "burst1" ? t("hunts.chart.sub.burst1") : "DPS"}
              >
                <div className="filters">
                  <label>{t("curves.metric")}
                    <select
                      value={metric}
                      onChange={(e) => setMetric(e.target.value as Metric)}
                    >
                      <option value="damage">{t("curves.metric.damage")}</option>
                      <option value="dps">{t("curves.metric.dps")}</option>
                      <option value="burst">{t("curves.metric.burst")}</option>
                      <option value="burst1">{t("curves.metric.burst1")}</option>
                    </select>
                  </label>
                </div>
                <div style={{ width: "100%", height: 260 }}>
                  <ResponsiveContainer>
                    <LineChart data={chartData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                      <XAxis
                        dataKey="t" minTickGap={40}
                        tickFormatter={(v: number) => fmtTime(v)}
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
                <p className="blurb">{t("hunts.chart.note", {
                  window: questMode ? t("hunts.chart.window.quest") : t("hunts.chart.window.engagement"),
                })}</p>
              </Collapsible>
              {(curve.survival ?? []).length > 0 && (
                <Collapsible title={t("hunts.survival")} subtitle={t("hunts.survival.sub")}>
                  <div className="table-wrap">
                    <table className="grid">
                      <thead>
                        <tr>
                          <th>{t("table.filter.hunter")}</th>
                          <th className="num">{t("hunts.survival.minHp")}</th>
                          <th className="num">&lt; 50%</th>
                          <th className="num">&lt; 25%</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(curve.survival ?? []).map((s) => (
                          <tr key={s.player}>
                            <td title={rankTitle(s.player)}>{s.player}</td>
                            <td className="num">{s.min_hp != null ? fmtPct(s.min_hp) : "—"}</td>
                            <td className="num">{fmtTime(s.time_below_50)}</td>
                            <td className="num">{fmtTime(s.time_below_25)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Collapsible>
              )}
              {highlights && highlights.awards.length > 0 && (
                <Collapsible title={t("hunts.highlights")} subtitle={t("hunts.highlights.sub")}>
                  <div className="table-wrap">
                    <table className="grid">
                      <thead>
                        <tr>
                          <th>{t("highlights.award")}</th>
                          {highlights.players.map((p) => (
                            <th key={p.player_id} className="num"
                              title={rankTitle(p.player, p.hunter_rank)}>
                              {p.player}{p.is_supporter ? ` ${t("hunts.npc")}` : ""}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {highlights.awards.map((a) => (
                          <tr key={a.id}>
                            <td title={a.explain ?? undefined}>{awardName(a.id, a.name)}</td>
                            {highlights.players.map((p) => {
                              const e = p.awards.find((x) => x.id === a.id);
                              return (
                                <td key={p.player_id} className="num">
                                  {e ? fmtAward(e.count, a.unit) : "—"}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                        <tr>
                          <td><strong>{t("hunts.damageShare")}</strong></td>
                          {highlights.players.map((p) => (
                            <td key={p.player_id} className="num">
                              {fmtPct(p.damage_share, 1)}
                            </td>
                          ))}
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </Collapsible>
              )}
            </>
          )}
        </div>
    </Modal>
  );
}

export default function HuntsView({ scope, weaponName, partySize, includeFailed }: { scope: number[]; weaponName: string | null; partySize: number | null; includeFailed: boolean }) {
  const { t, locale } = useT();
  const [monsterFilter, setMonsterFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  // The settings toggle sets the initial result filter; the local segmented
  // control still wins after that.
  const [resultFilter, setResultFilter] = useState<"" | "cleared" | "failed">(
    includeFailed ? "" : "cleared");
  const [selected, setSelected] = useState<HuntSummary | null>(null);

  const { data, error, loading } = useApi<{ hunts: HuntSummary[] }>("/hunts", {
    limit: 500,
    ...(scope.length > 0 && { player_ids: scope.join(",") }),
    ...(weaponName && { weapon_name: weaponName }),
    ...(partySize != null && { players: partySize }),
  });
  const hunts = data?.hunts ?? null;

  const monsters = useMemo(
    () => [...new Set((hunts ?? []).map((h) => h.monster))].sort(),
    [hunts]
  );
  // Monster id per captured name, for localized filter labels.
  const monsterIds = useMemo(
    () => new Map((hunts ?? []).map((h) => [h.monster, h.monster_id])),
    [hunts]
  );
  const filtered = useMemo(() => {
    let out = hunts ?? [];
    if (monsterFilter) out = out.filter((h) => h.monster === monsterFilter);
    if (resultFilter === "cleared") out = out.filter((h) => h.cleared);
    if (resultFilter === "failed") out = out.filter((h) => !h.cleared);

    const needle = search.trim().toLowerCase();
    if (needle) {
      out = out.filter((h) => {
        const party = (h.party ?? [])
          .flatMap((p) => [p.player, p.hunter_rank != null ? `hr ${p.hunter_rank}` : ""]);
        const awards = (h.highlight_award_ids ?? []).map((id, i) =>
          awardName(id, h.highlight_names?.[i]));
        return [
          String(h.id), `#${h.id}`,
          // Search what the user sees: localized labels, not the stored English.
          h.monster, monsterName(h.monster, h.monster_id),
          h.quest_id != null ? `#${h.quest_id}` : "",
          h.quest_id != null ? String(h.quest_id) : "",
          h.quest_stars != null ? `${h.quest_stars}★` : "",
          h.started_at, fmtDateTime(h.started_at),
          `${h.players}p`, t(h.cleared ? "hunts.cleared" : "hunts.failed"),
          h.source ?? "",
          ...party,
          ...(h.highlight_names ?? []),
          ...awards,
        ].join(" ").toLowerCase().includes(needle);
      });
    }
    return out;
  }, [hunts, monsterFilter, resultFilter, search, locale]);

  if (error || loading || !hunts) return <ApiState error={error} loading={loading} />;
  if (hunts.length === 0) {
    return (
      <EmptyState what={t("hunts.empty.what")}>
        <p>{t("hunts.empty.import")}</p>
      </EmptyState>
    );
  }

  const columns = makeColumns(t);

  return (
    <div className="card">
      <h2>{t("hunts.title", { count: filtered.length })}</h2>
      <div className="filters">
        <label className="hunt-search">{t("hunts.search.label")}
          <input type="search" value={search} placeholder={t("hunts.search.placeholder")}
            aria-label={t("hunts.search.aria")}
            onChange={(e) => setSearch(e.target.value)} />
        </label>
        <SearchSelect
          label={t("table.filter.monster")}
          value={monsterFilter}
          showAll
          options={monsters.map((m) => ({ value: m, label: monsterName(m, monsterIds.get(m)) }))}
          onChange={setMonsterFilter}
        />
        <div className="seg" role="group" aria-label={t("hunts.filter.result")}>
          <button type="button" className={resultFilter === "" ? "on" : ""}
            aria-pressed={resultFilter === ""}
            onClick={() => setResultFilter("")}>{t("common.all")}</button>
          <button type="button" className={resultFilter === "cleared" ? "on" : ""}
            aria-pressed={resultFilter === "cleared"}
            onClick={() => setResultFilter("cleared")}>{t("hunts.cleared")}</button>
          <button type="button" className={resultFilter === "failed" ? "on" : ""}
            aria-pressed={resultFilter === "failed"}
            onClick={() => setResultFilter("failed")}>{t("hunts.failed")}</button>
        </div>
      </div>
      <DataTable
        data={filtered}
        columns={columns}
        initialSort={[{ id: "date", desc: true }]}
        getRowId={(r) => String(r.id)}
        onRowClick={setSelected}
        isSelected={(r) => r.id === selected?.id}
      />
      {selected && <HuntPopup hunt={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
