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
import { useT, type TFn } from "@/lib/i18n";
import { weaponTypeName } from "@/lib/names";

interface WeaponRow {
  weapon: string; hunts: number; avg_dps: number;
  peak_dps: number; clear_rate: number;
}

function columnsFor(t: TFn): ColumnDef<WeaponRow>[] {
  return [
    { id: "weapon", accessorKey: "weapon", header: t("weapons.column.weapon"),
      cell: ({ row }) => weaponTypeName(row.original.weapon) },
    { id: "hunts", accessorKey: "hunts", header: t("weapons.column.hunts"), meta: { cls: "num" } },
    {
      id: "avg_dps", accessorKey: "avg_dps", header: t("weapons.column.avgDps"), meta: { cls: "num" },
      cell: ({ row }) => fmtDps(row.original.avg_dps),
    },
    {
      id: "peak_dps", accessorKey: "peak_dps", header: t("weapons.column.peak"),
      meta: { cls: "num" },
      cell: ({ row }) => fmtDps(row.original.peak_dps),
    },
    {
      id: "clear_rate", accessorKey: "clear_rate", header: t("weapons.column.clearPct"),
      meta: { cls: "num" },
      cell: ({ row }) => fmtPct(row.original.clear_rate),
    },
  ];
}

export default function WeaponsView({ scope, variantId, weaponName, clearScope, partySize, includeFailed }: { scope: number[]; variantId: number | string | null; weaponName: string | null; clearScope: () => void; partySize: number | null; includeFailed: boolean }) {
  const { t } = useT();
  const columns = columnsFor(t);
  const opts = useFilterOptions();
  const [monster, setMonster] = useState("");
  const [stars, setStars] = useState("");

  const { data, error, loading } = useApi<{ weapons: WeaponRow[] }>("/weapons", {
    ...(scope.length > 0 && { player_ids: scope.join(",") }),
    ...(monster && { monster_id: Number(monster) }),
    ...(stars && { stars: Number(stars) }),
    ...(variantId !== null && { variant_id: variantId }),
    ...(weaponName && { weapon_name: weaponName }),
    ...(partySize != null && { players: partySize }),
    ...(includeFailed && { include_failed: true }),
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
        <EmptyState what={t("weapons.empty.none")}><p>{t("weapons.empty.hint")}</p></EmptyState>
      </div>
    );
  }

  const chartData = [...rows].sort((a, b) => b.avg_dps - a.avg_dps);

  return (
    <div className="cards-2">
      <div className="card">
        {filters}
        <h2>{t("weapons.chart.heading")}</h2>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} layout="vertical">
            <CartesianGrid stroke={GRID_STROKE} />
            <XAxis type="number" tick={TICK}
              label={{ value: t("weapons.chart.xAxis"), fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, position: "insideBottom", offset: -2 }} />
            <YAxis type="category" dataKey="weapon" width={110} tick={{ ...TICK, fontSize: 12 }}
              tickFormatter={(v: string) => weaponTypeName(v)} />
            <ChartTip />
            <Bar dataKey="avg_dps" name={t("weapons.chart.series")} fill="#5aa9e6" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="card">
        <h2>{t("weapons.table.heading")}</h2>
        <DataTable
          data={rows}
          columns={columns}
          initialSort={[{ id: "avg_dps", desc: true }]}
          getRowId={(r) => r.weapon}
        />
        <p className="blurb">{t("weapons.table.note")}</p>
      </div>
    </div>
  );
}
