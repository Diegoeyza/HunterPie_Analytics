"use client";

import { useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { fmtPct, fmtTime } from "../../lib/format";
import { ApiState, useApi } from "../../lib/useApi";
import DataTable from "../DataTable";
import { MonsterSelect, StarsSelect } from "../FilterBar";
import { useFilterOptions } from "../useFilterOptions";
import EmptyState, { ScopeEmpty, scopeNames } from "../EmptyState";

interface Pairing {
  pairing: string; hunts: number; clear_rate: number;
  avg_clear_s: number | null; avg_share: Record<string, number>;
}

const columns: ColumnDef<Pairing>[] = [
  { id: "pairing", accessorKey: "pairing", header: "Pairing" },
  { id: "hunts", accessorKey: "hunts", header: "Hunts", meta: { cls: "num" } },
  {
    id: "clear_rate", accessorKey: "clear_rate", header: "Clear %",
    meta: { cls: "num" },
    cell: ({ row }) => fmtPct(row.original.clear_rate),
  },
  {
    id: "avg_clear_s", accessorFn: (r) => r.avg_clear_s ?? -1, header: "Avg clear",
    meta: { cls: "num" },
    cell: ({ row }) => fmtTime(row.original.avg_clear_s),
  },
  {
    id: "avg_share",
    accessorFn: (r) => Object.keys(r.avg_share).length,
    header: "Avg damage share",
    enableSorting: false,
    cell: ({ row }) => (
      Object.entries(row.original.avg_share)
        .map(([n, s]) => `${n} ${fmtPct(s)}`)
        .join(" · ")
    ),
  },
];

export default function SynergyView({ scope, variantId, clearScope, partySize }: { scope: number[]; variantId: number | string | null; clearScope: () => void; partySize: number | null }) {
  const opts = useFilterOptions();
  const [monster, setMonster] = useState("");
  const [stars, setStars] = useState("");

  const { data, error, loading } = useApi<{ pairings: Pairing[] }>("/synergy", {
    ...(scope.length > 0 && { player_ids: scope.join(",") }),
    ...(monster && { monster_id: Number(monster) }),
    ...(stars && { stars: Number(stars) }),
    ...(variantId !== null && { variant_id: variantId }),
    ...(partySize != null && { players: partySize }),
  });
  const rows = data?.pairings ?? null;

  const filters = (
    <div className="filters">
      <MonsterSelect value={monster} opts={opts}
        onChange={(v) => { setMonster(v); setStars(""); }} />
      <StarsSelect value={stars} onChange={setStars} monster={monster} opts={opts} />
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
          <ScopeEmpty names={scopeNames(scope, opts?.players)} onClear={clearScope} />
        </div>
      );
    }
    return (
      <div className="card">
        {filters}
        <EmptyState what="pairing data for these filters"><p>Try a different filter combination.</p></EmptyState>
      </div>
    );
  }

  return (
    <div className="card">
      {filters}
      <h2>Teammate pairings ({rows.length}) — click a header to sort</h2>
      <DataTable
        data={rows}
        columns={columns}
        initialSort={[{ id: "hunts", desc: true }]}
        getRowId={(r) => r.pairing}
      />
    </div>
  );
}
