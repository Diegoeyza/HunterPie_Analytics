"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { apiGet } from "../../lib/api";
import EmptyState from "../EmptyState";

interface WeaponRow {
  weapon: string; hunts: number; avg_dps: number;
  peak_dps: number; clear_rate: number;
}

type SortKey = keyof WeaponRow;

export default function WeaponsView({ scope }: { scope: number[] }) {
  const [rows, setRows] = useState<WeaponRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("avg_dps");
  const [desc, setDesc] = useState(true);

  useEffect(() => {
    apiGet<{ weapons: WeaponRow[] }>("/weapons", {
      ...(scope.length > 0 && { player_ids: scope.join(",") }),
    })
      .then((d) => setRows(d.weapons))
      .catch((e: Error) => setError(e.message));
  }, [scope.join(",")]);

  const sorted = useMemo(() => {
    if (!rows) return [];
    return [...rows].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      const cmp = typeof av === "string" ? av.localeCompare(bv as string)
        : (av as number) - (bv as number);
      return desc ? -cmp : cmp;
    });
  }, [rows, sortKey, desc]);

  if (error) return <p className="error">{error} — is the API running on :8000?</p>;
  if (!rows) return <p>Loading…</p>;
  if (rows.length === 0) {
    return (
      <EmptyState what="weapon data">
        <p>Seed some with <code>python -m app.seed --db hunts.db --hunts 50</code></p>
      </EmptyState>
    );
  }

  const toggle = (k: SortKey) => {
    if (k === sortKey) setDesc(!desc);
    else { setSortKey(k); setDesc(true); }
  };

  return (
    <>
      <div className="card">
        <h2>Average DPS by weapon</h2>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={sorted} layout="vertical">
            <CartesianGrid stroke="#2c313e" />
            <XAxis type="number" tick={{ fill: "#9aa1b2", fontSize: 11 }} />
            <YAxis type="category" dataKey="weapon" width={110} tick={{ fill: "#9aa1b2", fontSize: 12 }} />
            <Tooltip contentStyle={{ background: "#1d2029", border: "1px solid #2c313e" }} />
            <Bar dataKey="avg_dps" name="avg DPS" fill="#5aa9e6" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="card">
        <h2>Weapon performance matrix (click a header to sort)</h2>
        <table className="grid">
          <thead>
            <tr>
              <th onClick={() => toggle("weapon")}>Weapon</th>
              <th className="num" onClick={() => toggle("hunts")}>Hunts</th>
              <th className="num" onClick={() => toggle("avg_dps")}>Avg DPS</th>
              <th className="num" onClick={() => toggle("peak_dps")}>Peak DPS</th>
              <th className="num" onClick={() => toggle("clear_rate")}>Clear %</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.weapon}>
                <td>{r.weapon}</td>
                <td className="num">{r.hunts}</td>
                <td className="num">{r.avg_dps.toFixed(1)}</td>
                <td className="num">{r.peak_dps.toFixed(1)}</td>
                <td className="num">{(r.clear_rate * 100).toFixed(0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
