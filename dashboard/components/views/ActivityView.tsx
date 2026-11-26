"use client";

import type { ColumnDef } from "@tanstack/react-table";
import {Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, XAxis, YAxis, } from "recharts";
import { fmtDps, fmtInt, fmtPct } from "../../lib/format";
import { ApiState, useApi } from "../../lib/useApi";
import DataTable from "../DataTable";
import EmptyState from "../EmptyState";
import { ChartTip, GRID_STROKE, TICK } from "../ChartKit";
import { useT, type TFn } from "@/lib/i18n";

interface DayRow {
  date: string; hunts: number; clear_rate: number;
  avg_dps: number; total_damage: number;
}

function buildColumns(t: TFn): ColumnDef<DayRow>[] {
  return [
    { id: "date", accessorKey: "date", header: t("activity.table.date") },
    { id: "hunts", accessorKey: "hunts", header: t("activity.table.hunts"), meta: { cls: "num" } },
    {
      id: "clear_rate", accessorKey: "clear_rate", header: t("activity.table.clearPct"),
      meta: { cls: "num" },
      cell: ({ row }) => fmtPct(row.original.clear_rate),
    },
    {
      id: "avg_dps", accessorKey: "avg_dps", header: t("activity.table.avgDps"),
      meta: { cls: "num" },
      cell: ({ row }) => fmtDps(row.original.avg_dps),
    },
    {
      id: "total_damage", accessorKey: "total_damage", header: t("activity.table.damage"),
      meta: { cls: "num" },
      cell: ({ row }) => fmtInt(row.original.total_damage),
    },
  ];
}

export default function ActivityView({ partySize }: { partySize: number | null }) {
  const { t } = useT();
  const { data, error, loading } = useApi<{ days: DayRow[] }>("/activity", {
    ...(partySize != null && { players: partySize }),
  });
  const days = data?.days ?? null;

  if (error || loading || !days) return <ApiState error={error} loading={loading} />;
  if (days.length === 0) {
    return (
      <EmptyState what={t("activity.empty.what")}>
        <p>{t("activity.empty.hint")}</p>
      </EmptyState>
    );
  }

  const totalHunts = days.reduce((n, d) => n + d.hunts, 0);
  const totalDmg = days.reduce((n, d) => n + d.total_damage, 0);
  const summary = t(
    days.length === 1 ? "activity.summary.one" : "activity.summary.other",
    { hunts: fmtInt(totalHunts), damage: fmtInt(totalDmg), days: days.length },
  );

  return (
    <div className="cards-2">
      <div className="card">
        <h2>{summary}</h2>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={days}>
            <CartesianGrid stroke={GRID_STROKE} />
            <XAxis dataKey="date" tick={TICK} interval="preserveStartEnd" />
            <YAxis yAxisId="n" tick={TICK} allowDecimals={false}
              label={{ value: t("activity.chart.hunts"), fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, angle: -90, position: "insideLeft" }} />
            <YAxis yAxisId="rate" orientation="right" domain={[0, 1]}
              tick={TICK} tickFormatter={(v: number) => `${v * 100}%`}
              label={{ value: t("activity.chart.clearRate"), fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, angle: 90, position: "insideRight" }} />
            <ChartTip />
            <Bar yAxisId="n" dataKey="hunts" name={t("activity.chart.hunts")} fill="#5aa9e6" />
            <Line yAxisId="rate" type="monotone" dataKey="clear_rate" name={t("activity.chart.clearRate")}
              stroke="#58b368" dot={false} strokeWidth={2} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="card">
        <h2>{t("activity.table.title")}</h2>
        <DataTable
          data={days}
          columns={buildColumns(t)}
          initialSort={[{ id: "date", desc: true }]}
          getRowId={(d) => d.date}
        />
      </div>
    </div>
  );
}
