"use client";

import { useEffect, useState } from "react";
import { apiGet, type FilterOptions } from "../../lib/api";
import EmptyState from "../EmptyState";

interface PartyMember {
  player: string;
  weapon: string;
  dps: number;
}

interface HighScore {
  rank: number;
  hunt_id: number;
  date: string;
  monster: string;
  stars: number | null;
  clear_s: number | null;
  player: string;
  weapon: string;
  dps: number;
  party: PartyMember[];
}

const fmtTime = (s: number | null) =>
  s === null ? "—" : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

export default function HighScoreView() {
  const [opts, setOpts] = useState<FilterOptions | null>(null);
  const [player, setPlayer] = useState("");
  const [monster, setMonster] = useState("");
  const [weapon, setWeapon] = useState("");
  const [stars, setStars] = useState("");
  const [sortBy, setSortBy] = useState<"time" | "dps">("time");
  const [rows, setRows] = useState<HighScore[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<FilterOptions>("/filter-options").then(setOpts).catch(() => {});
  }, []);

  useEffect(() => {
    setError(null);
    apiGet<{ scores: HighScore[] }>("/high-scores", {
      ...(player && { player_id: Number(player) }),
      ...(monster && { monster_id: Number(monster) }),
      ...(weapon && { weapon_id: Number(weapon) }),
      ...(stars && { stars: Number(stars) }),
      sort_by: sortBy,
    }).then((d) => setRows(d.scores)).catch((e: Error) => setError(e.message));
  }, [player, monster, weapon, stars, sortBy]);

  if (error) return <p className="error">{error} — is the API running on :8000?</p>;
  if (!rows) return <p>Loading…</p>;

  const filters = (
    <div className="filters">
      {opts && (
        <>
          <label>Player
            <select value={player} onChange={(e) => setPlayer(e.target.value)}>
              <option value="">All</option>
              {opts.players.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label>Monster
            <select value={monster} onChange={(e) => { setMonster(e.target.value); setStars(""); }}>
              <option value="">All</option>
              {opts.monsters.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </label>
          <label>Weapon
            <select value={weapon} onChange={(e) => setWeapon(e.target.value)}>
              <option value="">All</option>
              {opts.weapons.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </label>
          <label>Stars
            <select value={stars} onChange={(e) => setStars(e.target.value)}>
              <option value="">All</option>
              {(monster ? (opts.monster_stars[Number(monster)] ?? []) : opts.stars).map((s) => (
                <option key={s} value={s}>{s}★</option>
              ))}
            </select>
          </label>
        </>
      )}
      <div className="seg" role="group" aria-label="Sort leaderboard">
        <button type="button" className={sortBy === "time" ? "on" : ""}
          aria-pressed={sortBy === "time"}
          onClick={() => setSortBy("time")}>Fastest clear</button>
        <button type="button" className={sortBy === "dps" ? "on" : ""}
          aria-pressed={sortBy === "dps"}
          onClick={() => setSortBy("dps")}>Highest DPS</button>
      </div>
    </div>
  );

  if (rows.length === 0) {
    return (
      <div className="card">
        {filters}
        <EmptyState what="cleared hunts match these filters">
          <p>Try a different filter combination or import more hunts.</p>
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="card">
      {filters}
      <h2>High scores ({rows.length}) — one row per hunter per cleared hunt</h2>
      <table className="grid">
        <thead>
          <tr>
            <th className="num">#</th>
            <th>Monster</th>
            <th className="num">★</th>
            <th className="num">Clear</th>
            <th>Date</th>
            <th>Player</th>
            <th>Weapon</th>
            <th className="num">DPS</th>
            <th>Party</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.hunt_id}-${r.player}`} className={r.rank === 1 ? "top" : ""}>
              <td className="num">{r.rank}</td>
              <td>{r.monster} <span className="num" title={`hunt #${r.hunt_id}`}>#{r.hunt_id}</span></td>
              <td className="num">{r.stars ?? "—"}</td>
              <td className="num">{fmtTime(r.clear_s)}</td>
              <td>{r.date}</td>
              <td>{r.player}</td>
              <td>{r.weapon}</td>
              <td className="num">{r.dps.toFixed(1)}</td>
              <td>
                {r.party.length === 0 ? "solo" : r.party.map((m) => (
                  <span key={m.player} className="party">
                    {m.player} ({m.weapon}) {m.dps.toFixed(1)}
                  </span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}