"use client";

import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { apiGet } from "../../lib/api";
import { fmtDps, fmtPct, fmtTime } from "../../lib/format";
import DataTable from "../DataTable";
import EmptyState from "../EmptyState";

interface QuestRow {
  quest_id: number | null; monster: string; stars: number | null;
  max_hp: number | null; hunts: number; carts: number; clear_rate: number;
  avg_clear_s: number | null;
  best_clear: { hunt_id: number; clear_s: number } | null;
  best_dps: number; enrage_uptime: number;
}

const columns: ColumnDef<QuestRow>[] = [
  {
    id: "quest", accessorFn: (r) => r.quest_id ?? -1, header: "Quest",
    cell: ({ row }) => (row.original.quest_id === null ? "—" : `#${row.original.quest_id}`),
  },
  { id: "monster", accessorKey: "monster", header: "Monster" },
  {
    id: "stars", accessorFn: (r) => r.stars ?? -1, header: "★",
    meta: { cls: "num" },
    cell: ({ row }) => (row.original.stars ?? "—"),
  },
  {
    id: "max_hp", accessorFn: (r) => r.max_hp ?? -1, header: "HP",
    meta: { cls: "num" },
    cell: ({ row }) => (row.original.max_hp ? Math.round(row.original.max_hp).toLocaleString() : "—"),
  },
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
    id: "best_clear", accessorFn: (r) => r.best_clear?.clear_s ?? -1, header: "Best clear",
    meta: { cls: "num" },
    cell: ({ row }) => (
      row.original.best_clear
        ? `#${row.original.best_clear.hunt_id} ${fmtTime(row.original.best_clear.clear_s)}`
        : "—"
    ),
  },
  {
    id: "best_dps", accessorKey: "best_dps", header: "Best DPS",
    meta: { cls: "num" },
    cell: ({ row }) => fmtDps(row.original.best_dps),
  },
  {
    id: "enrage_uptime", accessorKey: "enrage_uptime", header: "Enrage %",
    meta: { cls: "num" },
    cell: ({ row }) => fmtPct(row.original.enrage_uptime),
  },
  { id: "carts", accessorKey: "carts", header: "Carts", meta: { cls: "num" } },
];

export default function QuestsView() {
  const [rows, setRows] = useState<QuestRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ quests: QuestRow[] }>("/quests")
      .then((d) => setRows(d.quests))
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error} — is the API running?</p>;
  if (!rows) return <p>Loading…</p>;
  if (rows.length === 0) {
    return (
      <EmptyState what="quest data">
        <p>Import hunts first — quests appear once dumps carry quest ids.</p>
      </EmptyState>
    );
  }

  return (
    <div className="card">
      <h2>Quests ({rows.length}) — same monster, different HP per quest. Click a header to sort.</h2>
      <DataTable
        data={rows}
        columns={columns}
        initialSort={[{ id: "hunts", desc: true }]}
        // quest_id is null for untracked hunts (one row per hunt), so the
        // index keeps ids unique where quest_id alone would collide.
        getRowId={(r, i) => `${r.quest_id ?? "none"}-${r.monster}-${r.stars ?? "x"}-${i}`}
      />
    </div>
  );
}
