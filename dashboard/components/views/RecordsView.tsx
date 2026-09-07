"use client";

import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { apiGet } from "../../lib/api";
import { fmtDps, fmtTime } from "../../lib/format";
import DataTable from "../DataTable";
import EmptyState from "../EmptyState";

interface RecordRow {
  monster: string;
  hunts: number;
  fastest: { hunt_id: number; clear_s: number; date: string; party: string[]; carts: number } | null;
  top_dps: { hunt_id: number; player: string; weapon: string; dps: number; date: string } | null;
}

const columns: ColumnDef<RecordRow>[] = [
  { id: "monster", accessorKey: "monster", header: "Monster" },
  { id: "hunts", accessorKey: "hunts", header: "Hunts", meta: { cls: "num" } },
  {
    id: "fastest",
    accessorFn: (r) => r.fastest?.clear_s ?? -1,
    header: "Fastest clear",
    cell: ({ row }) => {
      const f = row.original.fastest;
      if (!f) return "no clears yet";
      const carts = f.carts > 0 ? ` · ${f.carts} cart${f.carts === 1 ? "" : "s"}` : " · deathless";
      return <>#{f.hunt_id} · {fmtTime(f.clear_s)} · {f.date} · {f.party.join(" + ")}{carts}</>;
    },
  },
  {
    id: "top_dps",
    accessorFn: (r) => r.top_dps?.dps ?? -1,
    header: "Top DPS",
    cell: ({ row }) => {
      const t = row.original.top_dps;
      if (!t) return "—";
      return <>{fmtDps(t.dps)} — {t.player} ({t.weapon}) · hunt #{t.hunt_id} · {t.date}</>;
    },
  },
];

export default function RecordsView() {
  const [rows, setRows] = useState<RecordRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ records: RecordRow[] }>("/records")
      .then((d) => setRows(d.records))
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error} — is the API running?</p>;
  if (!rows) return <p>Loading…</p>;
  if (rows.length === 0) {
    return (
      <EmptyState what="records">
        <p>Records appear after your first cleared hunt.</p>
      </EmptyState>
    );
  }

  return (
    <div className="card">
      <h2>Personal bests per monster — click a header to sort</h2>
      <DataTable
        data={rows}
        columns={columns}
        initialSort={[{ id: "hunts", desc: true }]}
        getRowId={(r) => r.monster}
      />
    </div>
  );
}
