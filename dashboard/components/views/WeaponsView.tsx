"use client";

import { useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import {Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis, } from "recharts";
import { fmtDps, fmtPct } from "../../lib/format";
import { ApiState, useApi } from "../../lib/useApi";
import DataTable from "../DataTable";
import { MonsterSelect, StarsSelect } from "../FilterBar";
import { useFilterOptions } from "../useFilterOptions";
import EmptyState, { ScopeEmpty, scopeNames } from "../EmptyState";
import { ChartTip, GRID_STROKE, TICK } from "../ChartKit";

interface WeaponRow {
  weapon: string; hunts: number; avg_dps: number;
  peak_dps: number; clear_rate: number;
}

const columns: ColumnDef<WeaponRow>[] = [
  { id: "weapon", accessorKey: "weapon", header: "Weapon" },
  { id: "hunts", accessorKey: "hunts", header: "Hunts", meta: { cls: "num" } },
  {
    id: "avg_dps", accessorKey: "avg_dps", header: "Avg DPS", meta: { cls: "num" },
    cell: ({ row }) => fmtDps(row.original.avg_dps),
  },
  {
    id: "peak_dps", accessorKey: "peak_dps", header: "Peak hit*",
    meta: { cls: "num" },
    cell: ({ row }) => fmtDps(row.original.peak_dps),
  },
  {
    id: "clear_rate", accessorKey: "clear_rate", header: "Clear %",
    meta: { cls: "num" },
    cell: ({ row }) => fmtPct(row.original.clear_rate),
  },
];

export default function WeaponsView({ scope, variantId, clearScope, partySize }: { scope: number[]; variantId: number | string | null; clearScope: () => void; partySize: number | null }) {
  const opts = useFilterOptions();
  const [monster, setMonster] = useState("");
  const [stars, setStars] = useState("");

  const { data, error, loading } = useApi<{ weapons: WeaponRow[] }>("/weapons", {
    ...(scope.length > 0 && { player_ids: scope.join(",") }),
    ...(monster && { monster_id: Number(monster) }),
    ...(stars && { stars: Number(stars) }),
    ...(variantId !== null && { variant_id: variantId }),
    ...(partySize != null && { players: partySize }),
  });
  const rows = data?.weapons ?? null;

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
        <EmptyState what="weapon data for these filters"><p>Try a different filter combination.</p></EmptyState>
      </div>
    );
  }

  const chartData = [...rows].sort((a, b) => b.avg_dps - a.avg_dps);

  return (
    <div className="cards-2">
      <div className="card">
        {filters}
        <h2>Average DPS by weapon</h2>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} layout="vertical">
            <CartesianGrid stroke={GRID_STROKE} />
            <XAxis type="number" tick={TICK}
              label={{ value: "average DPS", fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, position: "insideBottom", offset: -2 }} />
            <YAxis type="category" dataKey="weapon" width={110} tick={{ ...TICK, fontSize: 12 }} />
            <ChartTip />
            <Bar dataKey="avg_dps" name="avg DPS" fill="#5aa9e6" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="card">
        <h2>Weapon performance matrix (click a header to sort)</h2>
        <DataTable
          data={rows}
          columns={columns}
          initialSort={[{ id: "avg_dps", desc: true }]}
          getRowId={(r) => r.weapon}
        />
        <p className="blurb">* Peak hit = biggest single damage frame, not sustained DPS.</p>
      </div>
    </div>
  );
}
