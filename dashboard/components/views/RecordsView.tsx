"use client";

import { useEffect, useState } from "react";
import { apiGet } from "../../lib/api";
import EmptyState from "../EmptyState";

interface RecordRow {
  monster: string;
  hunts: number;
  fastest: { hunt_id: number; clear_s: number; date: string; party: string[]; carts: number } | null;
  top_dps: { hunt_id: number; player: string; weapon: string; dps: number; date: string } | null;
}

const fmtTime = (s: number) =>
  `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

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
    <>
      {rows.map((r) => (
        <div className="card" key={r.monster}>
          <h2>{r.monster} · {r.hunts} hunt{r.hunts === 1 ? "" : "s"}</h2>
          <table className="grid">
            <tbody>
              <tr>
                <td>⚡ Fastest clear</td>
                <td>
                  {r.fastest ? (
                    <>#{r.fastest.hunt_id} · {fmtTime(r.fastest.clear_s)} · {r.fastest.date} · {r.fastest.party.join(" + ")}{r.fastest.carts > 0 ? ` · ${r.fastest.carts} cart${r.fastest.carts === 1 ? "" : "s"}` : " · deathless"}</>
                  ) : "no clears yet"}
                </td>
              </tr>
              <tr>
                <td>💥 Top DPS</td>
                <td>
                  {r.top_dps ? (
                    <>{r.top_dps.dps.toFixed(1)} — {r.top_dps.player} ({r.top_dps.weapon}) · hunt #{r.top_dps.hunt_id} · {r.top_dps.date}</>
                  ) : "—"}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      ))}
    </>
  );
}
