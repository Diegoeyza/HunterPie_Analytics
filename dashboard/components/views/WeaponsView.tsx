"use client";

import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { apiGet } from "../../lib/api";
import { fmtDps, fmtPct } from "../../lib/format";
import DataTable from "../DataTable";
import SearchSelect from "../SearchSelect";
import { useFilterOptions } from "../useFilterOptions";
import EmptyState, { ScopeEmpty, scopeNames } from "../EmptyState";

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

export default function WeaponsView({ scope, variantId, clearScope }: { scope: number[]; variantId: number | string | null; clearScope: () => void }) {
  const [rows, setRows] = useState<WeaponRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const opts = useFilterOptions();
  const [monster, setMonster] = useState("");
  const [stars, setStars] = useState("");

  useEffect(() => {
    apiGet<{ weapons: WeaponRow[] }>("/weapons", {
      ...(scope.length > 0 && { player_ids: scope.join(",") }),
      ...(monster && { monster_id: Number(monster) }),
      ...(stars && { stars: Number(stars) }),
      ...(variantId !== null && { variant_id: variantId }),
    })
      .then((d) => setRows(d.weapons))
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
            <CartesianGrid stroke="#2c313e" />
            <XAxis type="number" tick={{ fill: "#9aa1b2", fontSize: 11 }}
              label={{ value: "average DPS", fill: "#9aa1b2", fontSize: 11, position: "insideBottom", offset: -2 }} />
            <YAxis type="category" dataKey="weapon" width={110} tick={{ fill: "#9aa1b2", fontSize: 12 }} />
            <Tooltip contentStyle={{ background: "#1d2029", border: "1px solid #2c313e" }} />
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
