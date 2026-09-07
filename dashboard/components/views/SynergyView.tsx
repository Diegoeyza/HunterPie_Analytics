"use client";

import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { apiGet } from "../../lib/api";
import { fmtDps, fmtPct, fmtTime } from "../../lib/format";
import DataTable from "../DataTable";
import SearchSelect from "../SearchSelect";
import { useFilterOptions } from "../useFilterOptions";
import EmptyState from "../EmptyState";

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
    cell: ({ row }) => (
      row.original.avg_clear_s ? `${Math.round(row.original.avg_clear_s)}s` : "—"
    ),
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

export default function SynergyView({ scope, variantId }: { scope: number[]; variantId: number | null }) {
  const [rows, setRows] = useState<Pairing[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const opts = useFilterOptions();
  const [monster, setMonster] = useState("");
  const [stars, setStars] = useState("");

  useEffect(() => {
    apiGet<{ pairings: Pairing[] }>("/synergy", {
      ...(scope.length > 0 && { player_ids: scope.join(",") }),
      ...(monster && { monster_id: Number(monster) }),
      ...(stars && { stars: Number(stars) }),
      ...(variantId !== null && { variant_id: variantId }),
    })
      .then((d) => setRows(d.pairings))
      .catch((e: Error) => setError(e.message));
  }, [scope.join(","), monster, stars, variantId]);

  if (error) return <p className="error">{error} — is the API running on :8000?</p>;
  if (!rows) return <p>Loading…</p>;

  const starOptions = monster ? (opts?.monster_stars[Number(monster)] ?? []) : opts?.stars ?? [];

  const filters = (
    <div className="filters">
      <SearchSelect
        label="Monster"
        value={monster}
        options={(opts?.monsters ?? []).map((m) => ({ value: String(m.id), label: m.name }))}
        onChange={(v) => { setMonster(v); setStars(""); }}
      />
      <label>Stars
        <select value={stars} onChange={(e) => setStars(e.target.value)}>
          <option value="">All</option>
          {starOptions.map((s) => <option key={s} value={s}>{s}★</option>)}
        </select>
      </label>
    </div>
  );

  if (rows.length === 0) {
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
