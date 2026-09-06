"use client";

import { useEffect, useState } from "react";
import { apiGet, type FilterOptions } from "../../lib/api";
import EmptyState from "../EmptyState";

interface Pairing {
  pairing: string; hunts: number; clear_rate: number;
  avg_clear_s: number | null; avg_share: Record<string, number>;
}

export default function SynergyView({ scope }: { scope: number[] }) {
  const [rows, setRows] = useState<Pairing[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [opts, setOpts] = useState<FilterOptions | null>(null);
  const [monster, setMonster] = useState("");
  const [stars, setStars] = useState("");

  useEffect(() => {
    apiGet<FilterOptions>("/filter-options").then(setOpts).catch(() => {});
  }, []);

  useEffect(() => {
    apiGet<{ pairings: Pairing[] }>("/synergy", {
      ...(scope.length > 0 && { player_ids: scope.join(",") }),
      ...(monster && { monster_id: Number(monster) }),
      ...(stars && { stars: Number(stars) }),
    })
      .then((d) => setRows(d.pairings))
      .catch((e: Error) => setError(e.message));
  }, [scope.join(","), monster, stars]);

  if (error) return <p className="error">{error} — is the API running on :8000?</p>;
  if (!rows) return <p>Loading…</p>;

  const filters = (
    <div className="filters">
      {opts && (
        <>
          <label>Monster
            <select value={monster} onChange={(e) => setMonster(e.target.value)}>
              <option value="">All</option>
              {opts.monsters.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </label>
          <label>Stars
            <select value={stars} onChange={(e) => setStars(e.target.value)}>
              <option value="">All</option>
              {opts.stars.map((s) => (
                <option key={s} value={s}>{s}★</option>
              ))}
            </select>
          </label>
        </>
      )}
    </div>
  );

  if (rows.length === 0) {
    return (
      <div className="card">
        {filters}
        <EmptyState what="pairing data for these filters"><p>Try a different filter combination.</p></EmptyState>
      </div>
    );
  }

  return (
    <div className="card">
      {filters}
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
