"use client";

import { useEffect, useState } from "react";
import { apiGet } from "../../lib/api";
import EmptyState from "../EmptyState";

interface Pairing {
  pairing: string; hunts: number; clear_rate: number;
  avg_clear_s: number | null; avg_share: Record<string, number>;
}

export default function SynergyView({ scope }: { scope: number[] }) {
  const [rows, setRows] = useState<Pairing[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ pairings: Pairing[] }>("/synergy", {
      ...(scope.length > 0 && { player_ids: scope.join(",") }),
    })
      .then((d) => setRows(d.pairings))
      .catch((e: Error) => setError(e.message));
  }, [scope.join(",")]);

  if (error) return <p className="error">{error} — is the API running on :8000?</p>;
  if (!rows) return <p>Loading…</p>;
  if (rows.length === 0) {
    return (
      <EmptyState what="pairing data">
        <p>Hunt with a party first — solo hunts appear here too, as pairings of one.</p>
      </EmptyState>
    );
  }

  return (
    <div className="card">
      <h2>Teammate pairings ({rows.length})</h2>
      <table className="grid">
        <thead>
          <tr>
            <th>Pairing</th>
            <th className="num">Hunts</th>
            <th className="num">Clear %</th>
            <th className="num">Avg clear</th>
            <th>Avg damage share</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.pairing}>
              <td>{r.pairing}</td>
              <td className="num">{r.hunts}</td>
              <td className="num">{(r.clear_rate * 100).toFixed(0)}%</td>
              <td className="num">
                {r.avg_clear_s ? `${Math.round(r.avg_clear_s)}s` : "—"}
              </td>
              <td>
                {Object.entries(r.avg_share)
                  .map(([n, s]) => `${n} ${(s * 100).toFixed(0)}%`)
                  .join(" · ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
