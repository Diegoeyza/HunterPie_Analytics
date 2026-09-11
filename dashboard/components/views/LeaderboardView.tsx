"use client";

import { useEffect, useMemo, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { apiGet } from "../../lib/api";
import { fmtDps } from "../../lib/format";
import DataTable from "../DataTable";
import SearchSelect from "../SearchSelect";
import { useFilterOptions } from "../useFilterOptions";
import EmptyState, { ScopeEmpty, scopeNames } from "../EmptyState";

interface Leader {
  player_id: number;
  player: string;
  hunts: number;
  avg_dps: number;
  best_dps: number;
}

const columns: ColumnDef<Leader>[] = [
  { id: "player", accessorKey: "player", header: "Player" },
  { id: "hunts", accessorKey: "hunts", header: "Hunts", meta: { cls: "num" } },
  {
    id: "avg_dps",
    accessorKey: "avg_dps",
    header: "Avg DPS",
    meta: { cls: "num" },
    cell: ({ row }) => fmtDps(row.original.avg_dps),
  },
  {
    id: "best_dps",
    accessorKey: "best_dps",
    header: "Best DPS",
    meta: { cls: "num" },
    cell: ({ row }) => fmtDps(row.original.best_dps),
  },
];

export default function LeaderboardView({ scope, variantId, clearScope }: { scope: number[]; variantId: number | string | null; clearScope: () => void }) {
  const opts = useFilterOptions();
  const [monster, setMonster] = useState("");
  const [weapon, setWeapon] = useState("");
  const [stars, setStars] = useState("");
  const [minHunts, setMinHunts] = useState(1);
  const [rows, setRows] = useState<Leader[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    apiGet<{ leaders: Leader[] }>("/leaderboard", {
      ...(scope.length > 0 && { player_ids: scope.join(",") }),
      ...(variantId !== null && { variant_id: variantId }),
      ...(monster && { monster_id: Number(monster) }),
      ...(weapon && { weapon_id: Number(weapon) }),
      ...(stars && { stars: Number(stars) }),
      min_hunts: minHunts,
    }).then((d) => setRows(d.leaders)).catch((e: Error) => setError(e.message));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope.join(","), variantId, monster, weapon, stars, minHunts]);

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
      <label>Min hunts
        <input type="number" min={1} value={minHunts}
          onChange={(e) => setMinHunts(Math.max(1, Number(e.target.value) || 1))} />
      </label>
    </div>
  );

  if (rows.length === 0) {
    if (scope.length > 0) {
      return (
        <div className="card">
          {filters}
          <ScopeEmpty names={scopeNames(scope, opts?.players)} onClear={clearScope}>
            <p>Try a lower min-hunts gate or a different filter combination.</p>
          </ScopeEmpty>
        </div>
      );
    }
    return (
      <div className="card">
        {filters}
        <EmptyState what="hunters match these filters">
          <p>Try a lower min-hunts gate or import more hunts.</p>
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="card">
      {filters}
      <h2>Best players by DPS — click a header to sort ({rows.length})</h2>
      <DataTable
        data={rows}
        columns={columns}
        initialSort={[{ id: "avg_dps", desc: true }]}
        getRowId={(r) => String(r.player_id)}
      />
    </div>
  );
}
