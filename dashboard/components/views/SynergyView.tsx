"use client";

import { useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { fmtClearTime, fmtPct } from "../../lib/format";
import { ApiState, useApi } from "../../lib/useApi";
import DataTable from "../DataTable";
import { MonsterSelect, StarsSelect } from "../FilterBar";
import { useFilterOptions } from "../useFilterOptions";
import EmptyState, { ScopeEmpty, scopeNames } from "../EmptyState";
import { useT, type TFn } from "@/lib/i18n";

interface Pairing {
  pairing: string; hunts: number; clear_rate: number;
  avg_clear_s: number | null; avg_share: Record<string, number>;
}

function buildColumns(t: TFn): ColumnDef<Pairing>[] {
  return [
    { id: "pairing", accessorKey: "pairing", header: t("synergy.table.pairing") },
    { id: "hunts", accessorKey: "hunts", header: t("synergy.table.hunts"), meta: { cls: "num" } },
    {
      id: "clear_rate", accessorKey: "clear_rate", header: t("synergy.table.clearPct"),
      meta: { cls: "num" },
      cell: ({ row }) => fmtPct(row.original.clear_rate),
    },
    {
      id: "avg_clear_s", accessorFn: (r) => r.avg_clear_s ?? -1, header: t("synergy.table.avgClear"),
      meta: { cls: "num" },
      cell: ({ row }) => fmtClearTime(row.original.avg_clear_s),
    },
    {
      id: "avg_share",
      accessorFn: (r) => Object.keys(r.avg_share).length,
      header: t("synergy.table.avgShare"),
      enableSorting: false,
      cell: ({ row }) => (
        Object.entries(row.original.avg_share)
          .map(([n, s]) => `${n} ${fmtPct(s)}`)
          .join(" · ")
      ),
    },
  ];
}

export default function SynergyView({ scope, variantId, clearScope, partySize, includeFailed }: { scope: number[]; variantId: number | string | null; clearScope: () => void; partySize: number | null; includeFailed: boolean }) {
  const { t } = useT();
  const opts = useFilterOptions();
  const [monster, setMonster] = useState("");
  const [stars, setStars] = useState("");

  const { data, error, loading } = useApi<{ pairings: Pairing[] }>("/synergy", {
    ...(scope.length > 0 && { player_ids: scope.join(",") }),
    ...(monster && { monster_id: Number(monster) }),
    ...(stars && { stars: Number(stars) }),
    ...(variantId !== null && { variant_id: variantId }),
    ...(partySize != null && { players: partySize }),
    ...(includeFailed && { include_failed: true }),
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
        <EmptyState what={t("synergy.empty.what")}><p>{t("synergy.empty.hint")}</p></EmptyState>
      </div>
    );
  }

  return (
    <div className="card">
      {filters}
      <h2>{t("synergy.title", { count: rows.length })}</h2>
      <DataTable
        data={rows}
        columns={buildColumns(t)}
        initialSort={[{ id: "hunts", desc: true }]}
        getRowId={(r) => r.pairing}
      />
    </div>
  );
}
