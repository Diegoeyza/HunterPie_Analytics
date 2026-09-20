"use client";

import { useEffect, useMemo, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { apiGet, type HuntSummary } from "../../lib/api";
import DataTable from "../DataTable";
import SearchSelect from "../SearchSelect";
import EmptyState from "../EmptyState";

interface AbnormalityEntry {
  id: string; name: string; category: string; start: number; end: number | null;
}
interface PlayerAbnormalities {
  player: string; abnormalities: AbnormalityEntry[];
}
interface BuffsData {
  hunt_id: number; monster: string; started_at: string;
  clear_s: number | null; players: PlayerAbnormalities[];
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
    cell: ({ row }) => `${Math.round(row.original.uptime_s)}s`,
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
function BuffTimeline({ lanes, domain }: { lanes: BuffLane[]; domain: number }) {
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * domain));
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
                const left = Math.max(0, Math.min(100, (w.start / domain) * 100));
                const width = Math.max(0.5, Math.min(100 - left, ((end - w.start) / domain) * 100));
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
            <span key={t} className="buff-tick" style={{ left: `${(t / domain) * 100}%` }}>
              {t}s
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
export default function BuffsView({ scope, partySize }: { scope: number[]; partySize: number | null }) {
  const [hunts, setHunts] = useState<HuntSummary[] | null>(null);
  const [huntId, setHuntId] = useState<number | null>(null);
  const [data, setData] = useState<BuffsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [catFilter, setCatFilter] = useState<string>("");
  const [view, setView] = useState<"table" | "timeline">("table");

  useEffect(() => {
    apiGet<{ hunts: HuntSummary[] }>("/hunts", {
      limit: 200,
      ...(partySize != null && { players: partySize }),
    })
      .then((d) => {
        setHunts(d.hunts);
        if (d.hunts.length > 0) setHuntId(d.hunts[0].id);
      })
      .catch((e: Error) => setError(e.message));
  }, [partySize]);

  useEffect(() => {
    if (huntId === null) return;
    apiGet<BuffsData>(`/hunts/${huntId}/abnormalities`)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [huntId]);

  const rows = useMemo((): UptimeRow[] => {
    if (!data) return [];
    const clearS = data.clear_s ?? 1;
    const result: UptimeRow[] = [];
    for (const p of data.players) {
      const byKey = new Map<string, UptimeRow>();
      for (const ab of p.abnormalities) {
        const key = `${ab.id}|${ab.category}`;
        const existing = byKey.get(key);
        const dur = (ab.end ?? clearS) - ab.start;
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
        row.pct = (row.uptime_s / clearS) * 100;
        result.push(row);
      }
    }
    return result;
  }, [data]);

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
    const byKey = new Map<string, BuffLane>();
    for (const p of data.players) {
      for (const ab of p.abnormalities) {
        const key = `${p.player}|${ab.id}|${ab.category}`;
        let lane = byKey.get(key);
        if (!lane) {
          lane = {
            player: p.player, id: ab.id, name: ab.name, category: ab.category,
            uptime_s: 0, pct: 0, activations: 0, windows: [],
          };
          byKey.set(key, lane);
        }
        lane.uptime_s += (ab.end ?? clearS) - ab.start;
        lane.activations += 1;
        lane.windows.push({ start: ab.start, end: ab.end, open: ab.end === null });
      }
    }
    const out = [...byKey.values()];
    for (const lane of out) {
      lane.pct = (lane.uptime_s / clearS) * 100;
      lane.windows.sort((a, b) => a.start - b.start);
    }
    out.sort((a, b) => b.pct - a.pct);
    if (!catFilter) return out;
    return out.filter((l) => l.category === catFilter);
  }, [data, catFilter]);

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
          label="Hunt"
          value={huntId === null ? "" : String(huntId)}
          showAll={false}
          options={(hunts ?? []).map((h) => ({
            value: String(h.id),
            label: `#${h.id} ${h.monster}${h.quest_stars ? ` ${h.quest_stars}★` : ""} · ${h.started_at.slice(0, 10)} · ${h.players}p`,
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
      </div>
      {data && (
        <>
          <h2>
            #{data.hunt_id} {data.monster}
            {data.clear_s ? ` · cleared in ${Math.round(data.clear_s)}s` : ""}
          </h2>
          {filtered.length === 0 ? (
            <p className="blurb">No abnormality data for this hunt. (Only HunterPie users have buff tracking.)</p>
          ) : view === "table" ? (
            <>
              <DataTable
                data={filtered}
                columns={columns}
                initialSort={[{ id: "pct", desc: true }]}
                getRowId={(r) => `${r.player}|${r.id}|${r.category}`}
              />
              <p className="blurb">Only HunterPie users have buff/debuff tracking data.</p>
            </>
          ) : (
            <>
              <BuffTimeline lanes={lanes} domain={domain} />
              <p className="blurb">Shaded = active. Hover a block for exact times. Open-ended blocks ran to quest end.</p>
            </>
          )}
        </>
      )}
    </div>
  );
}
