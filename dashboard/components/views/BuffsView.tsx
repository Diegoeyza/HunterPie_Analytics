"use client";

import { useEffect, useMemo, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import type { HuntSummary } from "../../lib/api";
import { fmtDate, fmtTime } from "../../lib/format";
import { ApiState, useApi } from "../../lib/useApi";
import DataTable from "../DataTable";
import SearchSelect from "../SearchSelect";
import { useFilterOptions } from "../useFilterOptions";

interface AbnormalityEntry {
  id: string; name: string; category: string; start: number; end: number | null;
}
interface PlayerAbnormalities {
  player: string; abnormalities: AbnormalityEntry[];
}
interface BuffsData {
  hunt_id: number; monster: string; started_at: string;
  clear_s: number | null; first_hit_s: number | null;
  players: PlayerAbnormalities[];
}

interface UptimeRow {
  player: string; id: string; name: string; category: string;
  uptime_s: number; pct: number; activations: number;
}

interface BuffWindow { start: number; end: number | null; open: boolean; }
interface BuffLane extends UptimeRow {
  windows: BuffWindow[];
}

const CATEGORY_COLORS: Record<string, string> = {
  Consumables: "#58b368",
  Skills: "#5aa9e6",
  Songs: "#e8b64c",
  Debuffs: "#e05c5c",
  Palico: "#9d7bff",
  Unknown: "#9aa1b2",
};

const columns: ColumnDef<UptimeRow>[] = [
  { id: "player", accessorKey: "player", header: "Hunter" },
  {
    id: "category", accessorKey: "category", header: "Category",
    cell: ({ row }) => (
      <span style={{ color: CATEGORY_COLORS[row.original.category] ?? "#9aa1b2" }}>
        {row.original.category}
      </span>
    ),
  },
  {
    id: "name", accessorKey: "name", header: "Abnormality",
    cell: ({ row }) => <span title={row.original.id}>{row.original.name}</span>,
  },
  {
    id: "uptime_s", accessorKey: "uptime_s", header: "Uptime",
    meta: { cls: "num" },
    cell: ({ row }) => fmtTime(row.original.uptime_s),
  },
  {
    id: "pct", accessorKey: "pct", header: "%",
    meta: { cls: "num" },
    cell: ({ row }) => `${row.original.pct.toFixed(1)}%`,
  },
  {
    id: "activations", accessorKey: "activations", header: "Activations",
    meta: { cls: "num" },
  },
];
/** Swimlane chart: one lane per hunter × buff, one shaded block per
 *  active window over fight time. Overlaps stack (no merging) so true
 *  uptime stays visible. */
function BuffTimeline({ lanes, domain, t0 }: { lanes: BuffLane[]; domain: number; t0: number }) {
  const span = Math.max(domain - t0, 0.001);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(t0 + f * span));
  return (
    <div className="buff-timeline">
      {lanes.map((lane) => {
        const color = CATEGORY_COLORS[lane.category] ?? "#9aa1b2";
        return (
          <div className="buff-lane" key={`${lane.player}|${lane.id}|${lane.category}`}>
            <div className="buff-lane-label" title={`${lane.player} · ${lane.id}`}>
              <span className="buff-dot" style={{ background: color }} />
              <span className="buff-lane-name">{lane.name}</span>
              <span className="buff-lane-player">{lane.player} · {lane.pct.toFixed(0)}%</span>
            </div>
            <div className="buff-track">
              {lane.windows.map((w, i) => {
                const end = w.end ?? domain;
                const left = Math.max(0, Math.min(100, ((w.start - t0) / span) * 100));
                const width = end <= t0 ? 0 : Math.max(0.5, Math.min(100 - left, ((end - Math.max(w.start, t0)) / span) * 100));
                return (
                  <div
                    key={i}
                    className="buff-window"
                    style={{ left: `${left}%`, width: `${width}%`, background: color }}
                    title={`${lane.player} · ${lane.name} · ${Math.round(w.start)}s–${Math.round(end)}s` +
                      ` (${Math.round(end - w.start)}s)${w.open ? " · active at quest end" : ""}`}
                  />
                );
              })}
            </div>
          </div>
        );
      })}
      <div className="buff-lane buff-axis">
        <div className="buff-lane-label" />
        <div className="buff-track buff-axis-track">
          {ticks.map((t) => (
            <span key={t} className="buff-tick" style={{ left: `${((t - t0) / span) * 100}%` }}>
              {fmtTime(t)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
export default function BuffsView({ scope, partySize }: { scope: number[]; partySize: number | null }) {
  const opts = useFilterOptions();
  const [huntId, setHuntId] = useState<number | null>(null);
  const [catFilter, setCatFilter] = useState<string>("");
  const [view, setView] = useState<"table" | "timeline">("table");
  const BASIS_KEY = "hpa.buffsBasis";
  const [basis, setBasis] = useState<"hunt" | "firstHit">(() => {
    try {
      return localStorage.getItem(BASIS_KEY) === "firstHit" ? "firstHit" : "hunt";
    } catch {
      return "hunt";
    }
  });
  const setBasisPersist = (b: "hunt" | "firstHit") => {
    setBasis(b);
    try {
      localStorage.setItem(BASIS_KEY, b);
    } catch { /* private mode: basis just won't persist */ }
  };
  // One list for every hunt. Buffs are stored per hunt and never merged across
  // hunts.
  const huntsQ = useApi<{ hunts: HuntSummary[] }>("/hunts", {
    limit: 200,
    ...(partySize != null && { players: partySize }),
  });
  const hunts = huntsQ.data?.hunts ?? null;
  // Newest hunt with buff data. The plain newest hunt may have none (the
  // companion wasn't running for it), which would make this tab look empty
  // even though older hunts have buff data.
  const latestWithBuffs = useMemo(
    () => hunts?.find((h) => h.has_buffs) ?? null, [hunts]);

  // Default to the latest hunt that has buff data; reset when the current
  // filters leave the selected hunt out of the list.
  useEffect(() => {
    if (!hunts || hunts.length === 0) return;
    if (huntId !== null && hunts.some((h) => h.id === huntId)) return;
    setHuntId((latestWithBuffs ?? hunts[0]).id);
  }, [hunts, latestWithBuffs, huntId]);

  const detailQ = useApi<BuffsData>(
    `/hunts/${huntId}/abnormalities`, huntId === null ? null : {});
  // Keyed fetch: ignore a stale previous-hunt payload while the new one loads.
  const rawData = detailQ.data && detailQ.data.hunt_id === huntId ? detailQ.data : null;

  // Honor the hunter scope: narrow lanes to scoped hunters by name.
  const data = useMemo(() => {
    if (!rawData || scope.length === 0) return rawData;
    const names = new Set((opts?.players ?? [])
      .filter((p) => scope.includes(p.id)).map((p) => p.name));
    return { ...rawData, players: rawData.players.filter((p) => names.has(p.player)) };
  }, [rawData, scope, opts]);

  const error = huntsQ.error ?? detailQ.error;
  const loadingList = huntsQ.loading;

  /** Clip origin for the uptime basis, shared by table, lanes, timeline. */
  const t0 = basis === "firstHit" && data?.first_hit_s != null ? data.first_hit_s : 0;

  const rows = useMemo((): UptimeRow[] => {
    if (!data) return [];
    const clearS = data.clear_s ?? 1;
    // Uptime basis: whole hunt (t=0) or clipped at the party's first hit.
    const denom = Math.max(clearS - t0, 0.001);
    const result: UptimeRow[] = [];
    for (const p of data.players) {
      const byKey = new Map<string, UptimeRow>();
      for (const ab of p.abnormalities) {
        // Windows closed before the uptime origin are not part of the fight:
        // pre-fight prep, or the loading-screen lead on a pre-fix import.
        if ((ab.end ?? clearS) <= t0) continue;
        const key = `${ab.id}|${ab.category}`;
        const existing = byKey.get(key);
        const dur = Math.max(0, Math.min(ab.end ?? clearS, clearS) - Math.max(ab.start, t0));
        if (existing) {
          existing.uptime_s += dur;
          existing.activations += 1;
        } else {
          byKey.set(key, {
            player: p.player, id: ab.id, name: ab.name, category: ab.category,
            uptime_s: dur, pct: 0, activations: 1,
          });
        }
      }
      for (const row of byKey.values()) {
        row.pct = (row.uptime_s / denom) * 100;
        result.push(row);
      }
    }
    return result;
  }, [data, basis]);

  const filtered = useMemo(() => {
    if (!catFilter) return rows;
    return rows.filter((r) => r.category === catFilter);
  }, [rows, catFilter]);

  /** Same grouping as the table, but keeping every activation window so
   *  the timeline can shade exactly when each buff was active. Sorted by
   *  uptime % desc to match the table's default order. */
  const lanes = useMemo((): BuffLane[] => {
    if (!data) return [];
    const clearS = data.clear_s ?? 1;
    const denom = Math.max(clearS - t0, 0.001);
    const byKey = new Map<string, BuffLane>();
    for (const p of data.players) {
      for (const ab of p.abnormalities) {
        if ((ab.end ?? clearS) <= t0) continue;  // closed before the origin
        const key = `${p.player}|${ab.id}|${ab.category}`;
        let lane = byKey.get(key);
        if (!lane) {
          lane = {
            player: p.player, id: ab.id, name: ab.name, category: ab.category,
            uptime_s: 0, pct: 0, activations: 0, windows: [],
          };
          byKey.set(key, lane);
        }
        lane.uptime_s += Math.max(0, Math.min(ab.end ?? clearS, clearS) - Math.max(ab.start, t0));
        lane.activations += 1;
        lane.windows.push({ start: ab.start, end: ab.end, open: ab.end === null });
      }
    }
    const out = [...byKey.values()];
    for (const lane of out) {
      lane.pct = (lane.uptime_s / denom) * 100;
      lane.windows.sort((a, b) => a.start - b.start);
    }
    out.sort((a, b) => b.pct - a.pct);
    if (!catFilter) return out;
    return out.filter((l) => l.category === catFilter);
  }, [data, catFilter, basis]);

  /** X domain: quest duration, or the furthest observed window end when
   *  clear_s is unknown (ongoing hunt). */
  const domain = useMemo(() => {
    if (data?.clear_s) return data.clear_s;
    let max = 0;
    for (const lane of lanes) {
      for (const w of lane.windows) max = Math.max(max, w.end ?? w.start);
    }
    return max > 0 ? max : 1;
  }, [data, lanes]);

  const categories = useMemo(() => [...new Set(rows.map((r) => r.category))].sort(), [rows]);

  if (error) return <ApiState error={error} loading={false} />;
  if (loadingList || !hunts) return <p>Loading…</p>;

  return (
    <div className="card">
      <div className="filters">
        <SearchSelect
          label="Hunt"
          value={huntId === null ? "" : String(huntId)}
          showAll={false}
          options={(hunts ?? []).map((h) => ({
            value: String(h.id),
            label: `#${h.id} ${h.monster}${h.quest_stars ? ` ${h.quest_stars}★` : ""} · ${fmtDate(h.started_at)} · ${h.players}p · ${h.source === "reframework" ? "mod" : "companion"}${h.has_buffs ? "" : " · no buffs"}`,
          }))}
          onChange={(v) => { if (v) setHuntId(Number(v)); }}
        />
        <label>Category
          <select value={catFilter} onChange={(e) => setCatFilter(e.target.value)}>
            <option value="">All</option>
            {categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        <div className="seg" role="group" aria-label="Buffs view">
          <button type="button" className={view === "table" ? "on" : ""}
            aria-pressed={view === "table"}
            onClick={() => setView("table")}>Table</button>
          <button type="button" className={view === "timeline" ? "on" : ""}
            aria-pressed={view === "timeline"}
            onClick={() => setView("timeline")}>Timeline</button>
        </div>
        <div className="seg" role="group" aria-label="Uptime basis">
          <button type="button" className={basis === "hunt" ? "on" : ""}
            aria-pressed={basis === "hunt"}
            onClick={() => setBasisPersist("hunt")}>Hunt start</button>
          <button type="button" className={basis === "firstHit" ? "on" : ""}
            aria-pressed={basis === "firstHit"}
            onClick={() => setBasisPersist("firstHit")}
            disabled={(data?.first_hit_s ?? null) === null}
            title={(data?.first_hit_s ?? null) === null
              ? "No damage data for this hunt"
              : `Measure uptime from first hit (${Math.round(data?.first_hit_s ?? 0)}s)`}>First hit</button>
        </div>
      </div>
      {hunts.length === 0 && (
        <p className="blurb">
          No hunts imported yet. Use the <b>HunterPie Analytics companion</b>
          (its own shortcut) before a quest, then Import.
        </p>
      )}
      {data && (
        <>
          <h2>
            #{data.hunt_id} {data.monster}
            {data.clear_s ? ` · cleared in ${fmtTime(data.clear_s)}` : ""}
          </h2>
          {filtered.length === 0 ? (
            catFilter ? (
              <p className="blurb">No {catFilter} data in this hunt.</p>
            ) : (rawData?.players.length ?? 0) > 0 ? (
              <p className="blurb">
                Buff data is only recorded for the local player. Clear the
                hunter filter (or select the player who hosted the quest).
              </p>
            ) : latestWithBuffs && latestWithBuffs.id !== huntId ? (
              <p className="blurb">
                The companion recorded no buffs for this hunt.{" "}
                <button type="button" onClick={() => setHuntId(latestWithBuffs.id)}>
                  Open the latest hunt with buffs
                </button>
              </p>
            ) : (
              <p className="blurb">
                No buff/debuff data yet. Run the <b>HunterPie Analytics
                companion</b> (its own shortcut) before a quest.
              </p>
            )
          ) : view === "table" ? (
            <>
              <DataTable
                data={filtered}
                columns={columns}
                initialSort={[{ id: "pct", desc: true }]}
                getRowId={(r) => `${r.player}|${r.id}|${r.category}`}
              />
              <p className="blurb">
                Recorded by the HunterPie Analytics companion for the local player.
              </p>
            </>
          ) : (
            <>
              <BuffTimeline lanes={lanes} domain={domain} t0={t0} />
              <p className="blurb">Shaded = active. Hover a block for exact times. Open-ended blocks ran to quest end.</p>
            </>
          )}
        </>
      )}
    </div>
  );
}
