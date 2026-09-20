"use client";

import { useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { fmtDps } from "../../lib/format";
import { ApiState, useApi } from "../../lib/useApi";
import DataTable from "../DataTable";
import { MonsterSelect, StarsSelect, WeaponSelect } from "../FilterBar";
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

export default function LeaderboardView({ scope, variantId, clearScope, partySize }: { scope: number[]; variantId: number | string | null; clearScope: () => void; partySize: number | null }) {
  const opts = useFilterOptions();
  const [monster, setMonster] = useState("");
  const [weapon, setWeapon] = useState("");
  const [stars, setStars] = useState("");
  const [minHunts, setMinHunts] = useState(1);
  const { data, error, loading } = useApi<{ leaders: Leader[] }>("/leaderboard", {
    ...(scope.length > 0 && { player_ids: scope.join(",") }),
    ...(variantId !== null && { variant_id: variantId }),
    ...(monster && { monster_id: Number(monster) }),
    ...(weapon && { weapon_id: Number(weapon) }),
    ...(stars && { stars: Number(stars) }),
    ...(partySize != null && { players: partySize }),
    min_hunts: minHunts,
  });
  const rows = data?.leaders ?? null;

  const filters = (
    <div className="filters">
      <MonsterSelect value={monster} opts={opts}
        onChange={(v) => { setMonster(v); setStars(""); }} />
      <WeaponSelect value={weapon} onChange={setWeapon} opts={opts} />
      <StarsSelect value={stars} onChange={setStars} monster={monster} opts={opts} />
      <label>Min hunts
        <input type="number" min={1} value={minHunts}
          onChange={(e) => setMinHunts(Math.max(1, Number(e.target.value) || 1))} />
      </label>
    </div>
  );

  if (error || loading || !rows) {
    return (
      <div className="card">
        {filters}
        <ApiState error={error} loading={loading} />
      </div>
    );
  }

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
