"use client";

import { useEffect, useState } from "react";
import { apiGet } from "../../lib/api";
import EmptyState from "../EmptyState";

interface QuestRow {
  quest_id: number | null; monster: string; stars: number | null;
  max_hp: number | null; hunts: number; carts: number; clear_rate: number;
  avg_clear_s: number | null;
  best_clear: { hunt_id: number; clear_s: number } | null;
  best_dps: number; enrage_uptime: number;
}

const fmtTime = (s: number | null) =>
  s === null ? "—" : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

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
      <h2>Quests ({rows.length}) — same monster, different HP per quest</h2>
      <table className="grid">
        <thead>
          <tr>
            <th>Quest</th>
            <th>Monster</th>
            <th className="num">★</th>
            <th className="num">HP</th>
            <th className="num">Hunts</th>
            <th className="num">Clear %</th>
            <th className="num">Avg clear</th>
            <th className="num">Best clear</th>
            <th className="num">Best DPS</th>
            <th className="num">Enrage %</th>
            <th className="num">Carts</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={String(r.quest_id)}>
              <td>{r.quest_id === null ? "—" : `#${r.quest_id}`}</td>
              <td>{r.monster}</td>
              <td className="num">{r.stars ?? "—"}</td>
              <td className="num">{r.max_hp ? Math.round(r.max_hp).toLocaleString() : "—"}</td>
              <td className="num">{r.hunts}</td>
              <td className="num">{(r.clear_rate * 100).toFixed(0)}%</td>
              <td className="num">{fmtTime(r.avg_clear_s)}</td>
              <td className="num">
                {r.best_clear ? `#${r.best_clear.hunt_id} ${fmtTime(r.best_clear.clear_s)}` : "—"}
              </td>
              <td className="num">{r.best_dps.toFixed(1)}</td>
              <td className="num">{(r.enrage_uptime * 100).toFixed(0)}%</td>
              <td className="num">{r.carts}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
