"use client";

import { useEffect, useState } from "react";
import { apiGet, apiSend, type Option, type Pin } from "../lib/api";

const SCOPE_KEY = "hp.scope";

export function loadScope(): number[] {
  try {
    const raw = localStorage.getItem(SCOPE_KEY);
    const ids = raw ? (JSON.parse(raw) as unknown) : [];
    return Array.isArray(ids) ? ids.filter((x) => typeof x === "number") : [];
  } catch {
    return [];
  }
}

interface Props {
  scope: number[];
  onScope: (ids: number[]) => void;
}

/** Hunter scope bar: star (pin) hunters, toggle who's in scope. Persisted. */
export default function ScopeBar({ scope, onScope }: Props) {
  const [players, setPlayers] = useState<Option[]>([]);
  const [pins, setPins] = useState<Pin[]>([]);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const refresh = () => {
    apiGet<{ players: Option[] }>("/filter-options")
      .then((d) => setPlayers(d.players)).catch(() => {});
    apiGet<{ pins: Pin[] }>("/players/pins").then((d) => setPins(d.pins)).catch(() => {});
  };
  useEffect(refresh, []);

  const pinnedIds = new Set(pins.map((p) => p.player_id));
  const byId = new Map(players.map((p) => [p.id, p.name]));

  const toggleScope = (id: number) => {
    onScope(scope.includes(id) ? scope.filter((s) => s !== id) : [...scope, id]);
    setOpen(false);
  };

  const togglePin = async (id: number) => {
    if (pinnedIds.has(id)) await apiSend("DELETE", `/players/${id}/pin`);
    else {
      await apiSend("POST", `/players/${id}/pin`);
      if (!scope.includes(id)) onScope([...scope, id]);
    }
    setOpen(false);
    refresh();
  };

  const q = query.trim().toLowerCase();
  const matches = q ? players.filter((p) => p.name.toLowerCase().includes(q)) : players;
  const shown = matches.slice(0, 100);

  return (
    <div className="scopebar">
      <span className="scope-label">Hunters:</span>
      {scope.length === 0 && <span className="scope-hint">all hunters</span>}
      {scope.map((id) => (
        <button key={id} className="chip" onClick={() => toggleScope(id)} title="remove from scope">
          {pinnedIds.has(id) ? "★ " : ""}{byId.get(id) ?? `#${id}`} ✕
        </button>
      ))}
      <div className="scope-picker">
        <button onClick={() => setOpen(!open)}>+ hunters</button>
        {open && (
          <div className="scope-menu">
            <input
              className="scope-search"
              placeholder="Search hunters…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {shown.map((p) => (
              <div key={p.id} className="scope-row">
                <button
                  className={scope.includes(p.id) ? "scope-name in" : "scope-name"}
                  onClick={() => toggleScope(p.id)}
                >
                  {p.name}
                </button>
                <button
                  className={pinnedIds.has(p.id) ? "star on" : "star"}
                  title={pinnedIds.has(p.id) ? "unpin" : "pin (star)"}
                  onClick={() => togglePin(p.id)}
                >
                  {pinnedIds.has(p.id) ? "★" : "☆"}
                </button>
              </div>
            ))}
            {players.length === 0 && <span className="scope-hint">no hunters yet</span>}
            {q && matches.length === 0 && <span className="scope-hint">no matches</span>}
            {matches.length > shown.length && (
              <span className="scope-hint">{matches.length} matches — keep typing to narrow</span>
            )}
          </div>
        )}
      </div>
      {scope.length > 0 && (
        <button className="scope-clear" onClick={() => onScope([])}>clear</button>
      )}
    </div>
  );
}
