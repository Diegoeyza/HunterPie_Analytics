"use client";

import type { ColumnDef } from "@tanstack/react-table";
import {Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, XAxis, YAxis, } from "recharts";
import { fmtDps, fmtInt, fmtPct } from "../../lib/format";
import { ApiState, useApi } from "../../lib/useApi";
import DataTable from "../DataTable";
import EmptyState from "../EmptyState";
import { ChartTip, GRID_STROKE, TICK } from "../ChartKit";

interface DayRow {
  date: string; hunts: number; clear_rate: number;
  avg_dps: number; total_damage: number;
}

const columns: ColumnDef<DayRow>[] = [
  { id: "date", accessorKey: "date", header: "Date" },
  { id: "hunts", accessorKey: "hunts", header: "Hunts", meta: { cls: "num" } },
  {
    id: "clear_rate", accessorKey: "clear_rate", header: "Clear %",
    meta: { cls: "num" },
    cell: ({ row }) => fmtPct(row.original.clear_rate),
  },
  {
    id: "avg_dps", accessorKey: "avg_dps", header: "Avg DPS",
    meta: { cls: "num" },
    cell: ({ row }) => fmtDps(row.original.avg_dps),
  },
  {
    id: "total_damage", accessorKey: "total_damage", header: "Damage",
    meta: { cls: "num" },
    cell: ({ row }) => fmtInt(row.original.total_damage),
  },
];

export default function ActivityView({ partySize }: { partySize: number | null }) {
  const { data, error, loading } = useApi<{ days: DayRow[] }>("/activity", {
    ...(partySize != null && { players: partySize }),
  });
  const days = data?.days ?? null;

  if (error || loading || !days) return <ApiState error={error} loading={loading} />;
  if (days.length === 0) {
    return (
      <EmptyState what="activity">
        <p>Hunt something first.</p>
      </EmptyState>
    );
  }

  const totalHunts = days.reduce((n, d) => n + d.hunts, 0);
  const totalDmg = days.reduce((n, d) => n + d.total_damage, 0);

  return (
    <div className="cards-2">
      <div className="card">
        <h2>
          {totalHunts} hunts · {fmtInt(totalDmg)} total damage · {days.length} active day{days.length === 1 ? "" : "s"}
        </h2>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={days}>
            <CartesianGrid stroke={GRID_STROKE} />
            <XAxis dataKey="date" tick={TICK} interval="preserveStartEnd" />
            <YAxis yAxisId="n" tick={TICK} allowDecimals={false}
              label={{ value: "hunts", fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, angle: -90, position: "insideLeft" }} />
            <YAxis yAxisId="rate" orientation="right" domain={[0, 1]}
              tick={TICK} tickFormatter={(v: number) => `${v * 100}%`}
              label={{ value: "clear rate", fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, angle: 90, position: "insideRight" }} />
            <ChartTip />
            <Bar yAxisId="n" dataKey="hunts" name="hunts" fill="#5aa9e6" />
            <Line yAxisId="rate" type="monotone" dataKey="clear_rate" name="clear rate"
              stroke="#58b368" dot={false} strokeWidth={2} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="card">
        <h2>By day — click a header to sort</h2>
        <DataTable
          data={days}
          columns={columns}
          initialSort={[{ id: "date", desc: true }]}
          getRowId={(d) => d.date}
        />
      </div>
    </div>
  );
}
