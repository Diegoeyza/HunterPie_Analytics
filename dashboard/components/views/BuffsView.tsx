"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, type HuntSummary } from "../../lib/api";
import EmptyState from "../EmptyState";

interface AbnormalityEntry {
  id: string; category: string; start: number; end: number | null;
}
interface PlayerAbnormalities {
  player: string; abnormalities: AbnormalityEntry[];
}
interface BuffsData {
  hunt_id: number; monster: string; started_at: string;
  clear_s: number | null; players: PlayerAbnormalities[];
}

interface UptimeRow {
  player: string; id: string; category: string;
  uptime_s: number; pct: number; activations: number;
}

const CATEGORY_COLORS: Record<string, string> = {
  Consumables: "#58b368",
  Skills: "#5aa9e6",
  Songs: "#e8b64c",
  Debuffs: "#e05c5c",
  Palico: "#9d7bff",
  Unknown: "#9aa1b2",
};

export default function BuffsView({ scope }: { scope: number[] }) {
  const [hunts, setHunts] = useState<HuntSummary[] | null>(null);
  const [huntId, setHuntId] = useState<number | null>(null);
  const [data, setData] = useState<BuffsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [catFilter, setCatFilter] = useState<string>("");

  useEffect(() => {
    apiGet<{ hunts: HuntSummary[] }>("/hunts", { limit: 200 })
      .then((d) => {
        setHunts(d.hunts);
        if (d.hunts.length > 0) setHuntId(d.hunts[0].id);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    if (huntId === null) return;
    apiGet<BuffsData>(`/hunts/${huntId}/abnormalities`)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [huntId]);

  const rows = useMemo((): UptimeRow[] => {
    if (!data) return [];
    const clearS = data.clear_s ?? 1;
    const result: UptimeRow[] = [];
    for (const p of data.players) {
      const byKey = new Map<string, UptimeRow>();
      for (const ab of p.abnormalities) {
        const key = `${ab.id}|${ab.category}`;
        const existing = byKey.get(key);
        const dur = (ab.end ?? clearS) - ab.start;
        if (existing) {
          existing.uptime_s += dur;
          existing.activations += 1;
        } else {
          byKey.set(key, {
            player: p.player, id: ab.id, category: ab.category,
            uptime_s: dur, pct: 0, activations: 1,
          });
        }
      }
      for (const row of byKey.values()) {
        row.pct = (row.uptime_s / clearS) * 100;
        result.push(row);
      }
    }
    return result;
  }, [data]);

  const filtered = useMemo(() => {
    if (!catFilter) return rows;
    return rows.filter((r) => r.category === catFilter);
  }, [rows, catFilter]);

  const categories = useMemo(() => [...new Set(rows.map((r) => r.category))].sort(), [rows]);

  if (error) return <p className="error">{error} — is the API running on :8000?</p>;
  if (!hunts) return <p>Loading…</p>;
  if (hunts.length === 0) {
    return (
      <EmptyState what="hunts">
        <p>Import one with <code>python -m app.import_hunt --db hunts.db --file hunt.json</code></p>
      </EmptyState>
    );
  }

  return (
    <div className="card">
      <div className="filters">
        <label>Hunt
          <select value={huntId ?? ""} onChange={(e) => setHuntId(Number(e.target.value))}>
            {hunts.map((h) => (
              <option key={h.id} value={h.id}>
                #{h.id} {h.monster} · {h.started_at.slice(0, 10)} · {h.players}p
              </option>
            ))}
          </select>
        </label>
        <label>Category
          <select value={catFilter} onChange={(e) => setCatFilter(e.target.value)}>
            <option value="">All</option>
            {categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
      </div>
      {data && (
        <>
          <h2>
            #{data.hunt_id} {data.monster}
            {data.clear_s ? ` · cleared in ${Math.round(data.clear_s)}s` : ""}
          </h2>
          {filtered.length === 0 ? (
            <p className="blurb">No abnormality data for this hunt. (Only HunterPie users have buff tracking.)</p>
          ) : (
            <>
              <table className="grid">
                <thead>
                  <tr>
                    <th>Hunter</th>
                    <th>Category</th>
                    <th>Abnormality</th>
                    <th className="num">Uptime</th>
                    <th className="num">%</th>
                    <th className="num">Activations</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r, i) => (
                    <tr key={i}>
                      <td>{r.player}</td>
                      <td>
                        <span style={{ color: CATEGORY_COLORS[r.category] ?? "#9aa1b2" }}>
                          {r.category}
                        </span>
                      </td>
                      <td title={r.id}>{r.id.split(".").pop()}</td>
                      <td className="num">{Math.round(r.uptime_s)}s</td>
                      <td className="num">{r.pct.toFixed(1)}%</td>
                      <td className="num">{r.activations}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="blurb">Only HunterPie users have buff/debuff tracking data.</p>
            </>
          )}
        </>
      )}
    </div>
  );
}
