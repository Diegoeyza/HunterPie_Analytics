"use client";

import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import {
  Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { apiGet } from "../../lib/api";
import { fmtDps, fmtPct } from "../../lib/format";
import DataTable from "../DataTable";
import EmptyState from "../EmptyState";

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
    cell: ({ row }) => Math.round(row.original.total_damage).toLocaleString(),
  },
];

export default function ActivityView() {
  const [days, setDays] = useState<DayRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ days: DayRow[] }>("/activity")
      .then((d) => setDays(d.days))
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error} — is the API running?</p>;
  if (!days) return <p>Loading…</p>;
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
          {totalHunts} hunts · {Math.round(totalDmg).toLocaleString()} total damage · {days.length} active day{days.length === 1 ? "" : "s"}
        </h2>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={days}>
            <CartesianGrid stroke="#2c313e" />
            <XAxis dataKey="date" tick={{ fill: "#9aa1b2", fontSize: 11 }} interval="preserveStartEnd" />
            <YAxis yAxisId="n" tick={{ fill: "#9aa1b2", fontSize: 11 }} allowDecimals={false}
              label={{ value: "hunts", fill: "#9aa1b2", fontSize: 11, angle: -90, position: "insideLeft" }} />
            <YAxis yAxisId="rate" orientation="right" domain={[0, 1]}
              tick={{ fill: "#9aa1b2", fontSize: 11 }} tickFormatter={(v: number) => `${v * 100}%`}
              label={{ value: "clear rate", fill: "#9aa1b2", fontSize: 11, angle: 90, position: "insideRight" }} />
            <Tooltip contentStyle={{ background: "#1d2029", border: "1px solid #2c313e" }} />
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
