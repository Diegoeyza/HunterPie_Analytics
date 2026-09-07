"use client";

import { useEffect, useMemo, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { apiGet } from "../../lib/api";
import { fmtDps, fmtTime } from "../../lib/format";
import DataTable from "../DataTable";
import SearchSelect from "../SearchSelect";
import { useFilterOptions } from "../useFilterOptions";
import EmptyState from "../EmptyState";

interface PartyMember {
  player: string;
  weapon: string;
  dps: number;
}

interface HighScore {
  rank: number;
  hunt_id: number;
  date: string;
  monster: string;
  stars: number | null;
  clear_s: number | null;
  player: string;
  weapon: string;
  dps: number;
  party: PartyMember[];
}

const columns: ColumnDef<HighScore>[] = [
  { id: "rank", accessorKey: "rank", header: "#", enableSorting: false, meta: { cls: "num" } },
  {
    id: "monster",
    accessorFn: (r) => r.monster,
    header: "Monster",
    cell: ({ row }) => (
      <>{row.original.monster}{" "}
        <span className="num" title={`hunt #${row.original.hunt_id}`}>#{row.original.hunt_id}</span>
      </>
    ),
  },
  {
    id: "stars",
    accessorFn: (r) => r.stars ?? -1,
    header: "★",
    meta: { cls: "num" },
    cell: ({ row }) => (row.original.stars ?? "—"),
  },
  {
    id: "clear_s",
    accessorFn: (r) => r.clear_s ?? -1,
    header: "Clear",
    meta: { cls: "num" },
    cell: ({ row }) => fmtTime(row.original.clear_s),
  },
  { id: "date", accessorKey: "date", header: "Date" },
  { id: "player", accessorKey: "player", header: "Player" },
  { id: "weapon", accessorKey: "weapon", header: "Weapon" },
  {
    id: "dps",
    accessorKey: "dps",
    header: "DPS",
    meta: { cls: "num" },
    cell: ({ row }) => fmtDps(row.original.dps),
  },
  {
    id: "party",
    accessorFn: (r) => r.party.length,
    header: "Party",
    enableSorting: false,
    cell: ({ row }) => (
      row.original.party.length === 0 ? "solo" : row.original.party.map((m) => (
        <span key={m.player} className="party">
          {m.player} ({m.weapon}) {fmtDps(m.dps)}
        </span>
      ))
    ),
  },
];

export default function HighScoreView({ scope }: { scope: number[] }) {
  const opts = useFilterOptions();
  const [monster, setMonster] = useState("");
  const [weapon, setWeapon] = useState("");
  const [stars, setStars] = useState("");
  const [sortBy, setSortBy] = useState<"time" | "dps">("dps");
  const [topN, setTopN] = useState("10");
  const [rows, setRows] = useState<HighScore[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    apiGet<{ scores: HighScore[] }>("/high-scores", {
      ...(scope.length > 0 && { player_ids: scope.join(",") }),
      ...(monster && { monster_id: Number(monster) }),
      ...(weapon && { weapon_id: Number(weapon) }),
      ...(stars && { stars: Number(stars) }),
      sort_by: sortBy,
      ...(topN && { limit: Number(topN) }),
    }).then((d) => setRows(d.scores)).catch((e: Error) => setError(e.message));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope.join(","), monster, weapon, stars, sortBy, topN]);

  const starOptions = useMemo(
    () => (monster ? (opts?.monster_stars[Number(monster)] ?? []) : opts?.stars ?? []),
    [opts, monster],
  );

  if (error) return <p className="error">{error} — is the API running on :8000?</p>;
  if (!rows) return <p>Loading…</p>;

  const filters = (
    <div className="filters">
      <SearchSelect
        label="Monster"
        value={monster}
        options={(opts?.monsters ?? []).map((m) => ({ value: String(m.id), label: m.name }))}
        onChange={(v) => { setMonster(v); setStars(""); }}
      />
      <SearchSelect
        label="Weapon"
        value={weapon}
        options={(opts?.weapons ?? []).map((w) => ({ value: String(w.id), label: w.name }))}
        onChange={setWeapon}
      />
      <label>Stars
        <select value={stars} onChange={(e) => setStars(e.target.value)}>
          <option value="">All</option>
          {starOptions.map((s) => <option key={s} value={s}>{s}★</option>)}
        </select>
      </label>
      <label>Top
        <select value={topN} onChange={(e) => setTopN(e.target.value)}>
          <option value="3">3</option>
          <option value="5">5</option>
          <option value="10">10</option>
          <option value="25">25</option>
          <option value="">All</option>
        </select>
      </label>
      <div className="seg" role="group" aria-label="Sort leaderboard">
        <button type="button" className={sortBy === "time" ? "on" : ""}
          aria-pressed={sortBy === "time"}
          onClick={() => setSortBy("time")}>Fastest clear</button>
        <button type="button" className={sortBy === "dps" ? "on" : ""}
          aria-pressed={sortBy === "dps"}
          onClick={() => setSortBy("dps")}>Highest DPS</button>
      </div>
    </div>
  );

  if (rows.length === 0) {
    return (
      <div className="card">
        {filters}
        <EmptyState what="cleared hunts match these filters">
          <p>Try a different filter combination or import more hunts.</p>
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="card">
      {filters}
      <h2>Top {topN || rows.length} hunts by {sortBy === "dps" ? "DPS" : "clear time"}{scope.length > 0 ? " — scoped hunters" : ""} ({rows.length})</h2>
      <DataTable
        data={rows}
        columns={columns}
        getRowId={(r) => `${r.hunt_id}-${r.player}`}
      />
    </div>
  );
}
