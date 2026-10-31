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
interface EnrageWindow { start: number; end: number | null; }
interface BuffsData {
  hunt_id: number; monster: string; started_at: string;
  clear_s: number | null; first_hit_s: number | null;
  enrage: EnrageWindow[];
  players: PlayerAbnormalities[];
}
interface MonsterStatusWindow {
  id: string; name: string; kind: string; start: number; end: number | null;
}
interface MonsterStatusData {
  hunt_id: number; monster: string; started_at: string;
  clear_s: number | null; first_hit_s: number | null;
  statuses: MonsterStatusWindow[];
}

/** Derived, not stored: Agitator is active while this hunt's monster is
 *  enraged. The id must never collide with a companion abnormality id. */
const AGITATOR_ID = "enrage.agitator";

interface UptimeRow {
  player: string; id: string; name: string; category: string;
  uptime_s: number; pct: number; activations: number;
}

interface BuffWindow { start: number; end: number | null; open: boolean; }
interface BuffLane extends UptimeRow {
  windows: BuffWindow[];
  /** Per-lane color (monster statuses); defaults to the category color. */
  color?: string;
  /** Right-hand lane caption; defaults to "player · pct%". */
  sublabel?: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  Consumables: "#58b368",
  Skills: "#5aa9e6",
  Songs: "#e8b64c",
  Debuffs: "#e05c5c",
  Palico: "#9d7bff",
  Unknown: "#9aa1b2",
};

/** One color per monster status; enrage stays red like the curve markers. */
const STATUS_COLORS: Record<string, string> = {
  enrage: "#e05c5c",
  "ailment.poison": "#a06cf0",
  "ailment.paralysis": "#e8b64c",
  "ailment.sleep": "#6f8fe8",
  "ailment.blast": "#e8843c",
  "ailment.exhaust": "#8fbf5a",
  "ailment.stun": "#e8d24c",
  "ailment.mount": "#5aa9e6",
  "ailment.flash": "#efe6a8",
  "ailment.dung": "#9a7b5c",
  "ailment.tranquilize": "#c77dff",
  "ailment.offset": "#5fd4c4",
  "ailment.powerclash": "#e05c9c",
  "ailment.bleed": "#c04545",
};
const statusColor = (id: string) => STATUS_COLORS[id] ?? "#9aa1b2";

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
        const color = lane.color ?? CATEGORY_COLORS[lane.category] ?? "#9aa1b2";
        const caption = lane.sublabel
          ?? `${lane.player ? `${lane.player} · ` : ""}${lane.pct.toFixed(0)}%`;
        return (
          <div className="buff-lane" key={`${lane.player}|${lane.id}|${lane.category}`}>
            <div className="buff-lane-label" title={`${lane.player ? `${lane.player} · ` : ""}${lane.id}`}>
              <span className="buff-dot" style={{ background: color }} />
              <span className="buff-lane-name">{lane.name}</span>
              <span className="buff-lane-player">{caption}</span>
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
  // Toggle: add the derived Agitator row/lane (monster enrage uptime).
  const AGITATOR_KEY = "hpa.buffsAgitator";
  const [showAgitator, setShowAgitator] = useState<boolean>(() => {
    try {
      return localStorage.getItem(AGITATOR_KEY) === "1";
    } catch {
      return false;
    }
  });
  const setAgitatorPersist = (v: boolean) => {
    setShowAgitator(v);
    try {
      localStorage.setItem(AGITATOR_KEY, v ? "1" : "0");
    } catch { /* private mode: toggle just won't persist */ }
  };
  // Sub-tab: player buffs (what the companion records) vs the monster's
  // own status windows. No toggle is meaningful on the Monster side, so it
  // is hidden there and persists independently of the player controls.
  const BUFFS_TAB_KEY = "hpa.buffsTab";
  const [buffsTab, setBuffsTab] = useState<"hunters" | "monster">(() => {
    try {
      return localStorage.getItem(BUFFS_TAB_KEY) === "monster" ? "monster" : "hunters";
    } catch {
      return "hunters";
    }
  });
  const setBuffsTabPersist = (t: "hunters" | "monster") => {
    setBuffsTab(t);
    try {
      localStorage.setItem(BUFFS_TAB_KEY, t);
    } catch { /* private mode: tab just won't persist */ }
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
  // Monster side: fetched only while that sub-tab is open.
  const statusQ = useApi<MonsterStatusData>(
    `/hunts/${huntId}/monster-status`,
    huntId === null || buffsTab !== "monster" ? null : {});
  const statusData = statusQ.data && statusQ.data.hunt_id === huntId ? statusQ.data : null;

  // Honor the hunter scope: narrow lanes to scoped hunters by name.
  const data = useMemo(() => {
    if (!rawData || scope.length === 0) return rawData;
    const names = new Set((opts?.players ?? [])
      .filter((p) => scope.includes(p.id)).map((p) => p.name));
    return { ...rawData, players: rawData.players.filter((p) => names.has(p.player)) };
  }, [rawData, scope, opts]);

  const error = huntsQ.error
    ?? (buffsTab === "monster" ? statusQ.error : detailQ.error);
  const loadingList = huntsQ.loading;

  /** Clip origin for the uptime basis, shared by table, lanes, timeline. */
  const t0 = basis === "firstHit" && data?.first_hit_s != null ? data.first_hit_s : 0;
  const statusT0 = basis === "firstHit" && statusData?.first_hit_s != null
    ? statusData.first_hit_s
    : 0;

  /** Derived Agitator row/lane: uptime is the monster's enrage windows,
   *  measured with the same origin/denominator as every recorded buff.
   *  One quest-wide row (the skill is player-side but the trigger is the
   *  monster, and buffs are companion-recorded for the local player only). */
  const agitator = useMemo((): { row: UptimeRow; lane: BuffLane } | null => {
    if (!data || !showAgitator || data.enrage.length === 0) return null;
    const clearS = data.clear_s ?? 1;
    const denom = Math.max(clearS - t0, 0.001);
    let uptime = 0;
    let activations = 0;
    const windows: BuffWindow[] = [];
    for (const w of data.enrage) {
      const end = w.end ?? clearS;
      if (end <= t0) continue;  // enrage closed before the uptime origin
      uptime += Math.max(0, Math.min(end, clearS) - Math.max(w.start, t0));
      activations += 1;
      windows.push({ start: w.start, end: w.end, open: w.end === null });
    }
    if (activations === 0) return null;
    windows.sort((a, b) => a.start - b.start);
    const base = {
      player: "—", id: AGITATOR_ID, name: "Agitator", category: "Skills",
      uptime_s: uptime, pct: (uptime / denom) * 100, activations,
    };
    return { row: base, lane: { ...base, windows } };
  }, [data, showAgitator, t0]);

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
    if (agitator) result.push(agitator.row);
    return result;
  }, [data, basis, agitator]);

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
    if (agitator) out.push(agitator.lane);
    out.sort((a, b) => b.pct - a.pct);
    if (!catFilter) return out;
    return out.filter((l) => l.category === catFilter);
  }, [data, catFilter, basis, agitator]);

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

  /** Monster lanes: one per status (enrage + ailments), grouped like buffs but
   *  without a player dimension. The backend merges overlapping slots per
   *  status, so summing windows can't double-count. */
  const monsterLanes = useMemo((): BuffLane[] => {
    if (!statusData) return [];
    const clearS = statusData.clear_s ?? 1;
    const denom = Math.max(clearS - statusT0, 0.001);
    const byKey = new Map<string, BuffLane>();
    for (const s of statusData.statuses) {
      if ((s.end ?? clearS) <= statusT0) continue;
      let lane = byKey.get(s.id);
      if (!lane) {
        lane = {
          player: "", id: s.id, name: s.name, category: s.kind,
          color: statusColor(s.id), uptime_s: 0, pct: 0, activations: 0,
          windows: [],
        };
        byKey.set(s.id, lane);
      }
      lane.uptime_s += Math.max(
        0, Math.min(s.end ?? clearS, clearS) - Math.max(s.start, statusT0));
      lane.activations += 1;
      lane.windows.push({ start: s.start, end: s.end, open: s.end === null });
    }
    const out = [...byKey.values()];
    for (const lane of out) {
      lane.pct = (lane.uptime_s / denom) * 100;
      lane.windows.sort((a, b) => a.start - b.start);
      lane.sublabel = `${lane.activations}× · ${lane.pct.toFixed(0)}%`;
    }
    out.sort((a, b) => b.pct - a.pct);
    return out;
  }, [statusData, statusT0]);

  const monsterDomain = useMemo(() => {
    if (statusData?.clear_s) return statusData.clear_s;
    let max = 0;
    for (const lane of monsterLanes) {
      for (const w of lane.windows) max = Math.max(max, w.end ?? w.start);
    }
    return max > 0 ? max : 1;
  }, [statusData, monsterLanes]);

  /** Basis availability follows the visible side's payload. */
  const activeFirstHit = buffsTab === "monster"
    ? (statusData?.first_hit_s ?? null)
    : (data?.first_hit_s ?? null);
  const isModHunt = (hunts?.find((h) => h.id === huntId)?.source ?? "") === "reframework";

  const categories = useMemo(() => [...new Set(rows.map((r) => r.category))].sort(), [rows]);

  if (error) return <ApiState error={error} loading={false} />;
  if (loadingList || !hunts) return <p>Loading…</p>;

  return (
    <div className="card">
      <nav className="subtabs" role="tablist" aria-label="Buffs">
        <button type="button" role="tab" aria-selected={buffsTab === "hunters"}
          className={buffsTab === "hunters" ? "active" : ""}
          onClick={() => setBuffsTabPersist("hunters")}>Hunters</button>
        <button type="button" role="tab" aria-selected={buffsTab === "monster"}
          className={buffsTab === "monster" ? "active" : ""}
          onClick={() => setBuffsTabPersist("monster")}>Monster</button>
      </nav>
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
        {buffsTab === "hunters" && (
          <>
            <label>Category
              <select value={catFilter} onChange={(e) => setCatFilter(e.target.value)}>
                <option value="">All</option>
                {categories.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </label>
            <div className="seg" role="group" aria-label="Derived buffs">
              <button
                type="button"
                className={showAgitator ? "on" : ""}
                aria-pressed={showAgitator}
                onClick={() => setAgitatorPersist(!showAgitator)}
                title="Show Agitator uptime, derived from the monster's enrage windows"
              >
                Agitator
              </button>
            </div>
            <div className="seg" role="group" aria-label="Buffs view">
              <button type="button" className={view === "table" ? "on" : ""}
                aria-pressed={view === "table"}
                onClick={() => setView("table")}>Table</button>
              <button type="button" className={view === "timeline" ? "on" : ""}
                aria-pressed={view === "timeline"}
                onClick={() => setView("timeline")}>Timeline</button>
            </div>
          </>
        )}
        <div className="seg" role="group" aria-label="Uptime basis">
          <button type="button" className={basis === "hunt" ? "on" : ""}
            aria-pressed={basis === "hunt"}
            onClick={() => setBasisPersist("hunt")}>Hunt start</button>
          <button type="button" className={basis === "firstHit" ? "on" : ""}
            aria-pressed={basis === "firstHit"}
            onClick={() => setBasisPersist("firstHit")}
            disabled={activeFirstHit === null}
            title={activeFirstHit === null
              ? "No damage data for this hunt"
              : `Measure uptime from first hit (${Math.round(activeFirstHit)}s)`}>First hit</button>
        </div>
      </div>
      {hunts.length === 0 && (
        <p className="blurb">
          No hunts imported yet. Use the <b>HunterPie Analytics companion</b>
          (its own shortcut) before a quest, then Import.
        </p>
      )}
      {buffsTab === "hunters" ? (
        data && (
          <>
            <h2>
              #{data.hunt_id} {data.monster}
              {data.clear_s ? ` · cleared in ${fmtTime(data.clear_s)}` : ""}
            </h2>
            {showAgitator && data.enrage.length === 0 && (
              <p className="blurb">
                No enrage windows recorded for this hunt, so Agitator cannot be
                derived. Enrage is recorded by the <b>HunterPie Analytics
                companion</b>.
              </p>
            )}
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
                  {agitator
                    ? " Agitator is derived from this hunt's monster enrage windows, not from your build."
                    : ""}
                </p>
              </>
            ) : (
              <>
                <BuffTimeline lanes={lanes} domain={domain} t0={t0} />
                <p className="blurb">
                  Shaded = active. Hover a block for exact times. Open-ended
                  blocks ran to quest end.
                  {agitator
                    ? " The Agitator lane is derived from the monster's enrage windows."
                    : ""}
                </p>
              </>
            )}
          </>
        )
      ) : statusData ? (
        <>
          <h2>
            #{statusData.hunt_id} {statusData.monster}
            {statusData.clear_s ? ` · cleared in ${fmtTime(statusData.clear_s)}` : ""}
          </h2>
          {monsterLanes.length === 0 ? (
            isModHunt ? (
              <p className="blurb">
                Monster statuses are recorded by the <b>HunterPie Analytics
                companion</b>. This hunt was captured by the REFramework mod
                only, which does not track monster statuses.
              </p>
            ) : (
              <p className="blurb">
                No monster status windows recorded for this hunt. The companion
                records enrage and ailment activations; older dumps may predate
                this.
              </p>
            )
          ) : (
            <>
              <BuffTimeline lanes={monsterLanes} domain={monsterDomain} t0={statusT0} />
              <p className="blurb">
                Shaded = status active. Hover a block for exact times and
                duration (for example, how long a poison lasted). One lane per
                status, including enrage.
              </p>
              {statusData.statuses.length > 0 &&
                !statusData.statuses.some((s) => s.id.startsWith("ailment.")) && (
                  <p className="blurb">
                    This hunt only has enrage. Poison, stun, mount and the other
                    ailments start with hunts captured by the updated companion
                    build.
                  </p>
                )}
            </>
          )}
        </>
      ) : statusQ.loading ? (
        <p>Loading…</p>
      ) : null}
    </div>
  );
}
