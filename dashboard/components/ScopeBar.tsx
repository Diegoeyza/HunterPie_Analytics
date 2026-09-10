"use client";

import { useEffect, useState } from "react";
import {
  apiGetCached, apiInvalidate, apiSend, variantLabel, UNKNOWN_VARIANT_ID,
  type Option, type Pin, type PlayerVariants,
} from "../lib/api";
import SearchSelect from "./SearchSelect";
import WeaponVariantManager from "./WeaponVariantManager";

const SCOPE_KEY = "hp.scope";
const VARIANT_KEY = "hp.variant";

export function loadScope(): number[] {
  try {
    const raw = localStorage.getItem(SCOPE_KEY);
    const ids = raw ? (JSON.parse(raw) as unknown) : [];
    return Array.isArray(ids) ? ids.filter((x) => typeof x === "number") : [];
  } catch {
    return [];
  }
}

export function loadVariant(): number | null {
  try {
    const raw = localStorage.getItem(VARIANT_KEY);
    const v = raw ? (JSON.parse(raw) as unknown) : null;
    return typeof v === "number" ? v : null;
  } catch {
    return null;
  }
}

export function storeVariant(id: number | null) {
  try {
    localStorage.setItem(VARIANT_KEY, JSON.stringify(id));
  } catch { /* private mode: variant just won't persist */ }
}

interface Props {
  scope: number[];
  onScope: (ids: number[]) => void;
  variantId: number | null;
  onVariant: (id: number | null) => void;
}

/** Hunter scope bar: star (pin) hunters, toggle who's in scope. Persisted.
 *  With exactly one scoped hunter who has gear data, a weapon-variant
 *  filter appears next to the hunter chips, with an edit button that
 *  opens the label-once naming menu. */
export default function ScopeBar({ scope, onScope, variantId, onVariant }: Props) {
  const [players, setPlayers] = useState<Option[]>([]);
  const [pins, setPins] = useState<Pin[]>([]);
  const [variants, setVariants] = useState<PlayerVariants | null>(null);
  const [open, setOpen] = useState(false);
  const [variantMenu, setVariantMenu] = useState(false);
  const [query, setQuery] = useState("");

  const refresh = () => {
    apiGetCached<{ players: Option[] }>("/filter-options")
      .then((d) => setPlayers(d.players)).catch(() => {});
    apiGetCached<{ pins: Pin[] }>("/players/pins").then((d) => setPins(d.pins)).catch(() => {});
  };
  useEffect(refresh, []);

  const loadVariants = (playerId: number) => {
    apiGetCached<PlayerVariants>(`/players/${playerId}/variants`)
      .then(setVariants).catch(() => {});
  };

  // Variant options only exist for a single scoped hunter with gear data.
  useEffect(() => {
    setVariants(null);
    setVariantMenu(false);
    if (scope.length !== 1) {
      if (variantId !== null) onVariant(null);
      return;
    }
    loadVariants(scope[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope.join(",")]);

  // Drop a persisted variant the hunter no longer has (e.g. DB rebuild).
  useEffect(() => {
    if (variantId === null || variants === null) return;
    const ok = variantId === UNKNOWN_VARIANT_ID
      ? variants.unknown_hunts > 0
      : variants.variants.some((v) => v.id === variantId);
    if (!ok) onVariant(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [variants]);

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
    apiInvalidate();
    refresh();
  };

  const q = query.trim().toLowerCase();
  const hit = (name: string) => !q || name.toLowerCase().includes(q);
  // Starred hunters stay fixed on top, then everyone else — both alphabetical.
  const starred = pins
    .map((p) => ({ id: p.player_id, name: byId.get(p.player_id) ?? p.name }))
    .filter((p) => hit(p.name))
    .sort((a, b) => a.name.localeCompare(b.name));
  const rest = players
    .filter((p) => !pinnedIds.has(p.id) && hit(p.name))
    .sort((a, b) => a.name.localeCompare(b.name));
  const matchCount = starred.length + rest.length;
  const shownRest = rest.slice(0, Math.max(0, 100 - starred.length));

  // The filter only appears once the hunter has real fingerprint data;
  // "Unknown (pre-gear hunts)" joins the options when those exist too.
  const hasVariants = variants !== null && variants.variants.length > 0;
  const variantOptions = [
    ...(variants?.variants ?? []).map((v) => ({
      value: String(v.id ?? `fp:${v.weapon_type}:${v.raw}:${v.element}:${v.affinity}`),
      label: `${variantLabel(v)} · ${v.hunts} hunt${v.hunts === 1 ? "" : "s"}`,
    })),
    ...((variants?.unknown_hunts ?? 0) > 0 ? [{
      value: String(UNKNOWN_VARIANT_ID),
      label: `Unknown (pre-gear hunts) · ${variants!.unknown_hunts} hunt${variants!.unknown_hunts === 1 ? "" : "s"}`,
    }] : []),
  ];

  const row = (p: { id: number; name: string }) => (
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
  );

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
            {starred.length > 0 && (
              <>
                <div className="scope-section">Starred</div>
                {starred.map(row)}
              </>
            )}
            {starred.length > 0 && shownRest.length > 0 && <div className="scope-div" />}
            {shownRest.map(row)}
            {players.length === 0 && <span className="scope-hint">no hunters yet</span>}
            {q && matchCount === 0 && <span className="scope-hint">no matches</span>}
            {matchCount > starred.length + shownRest.length && (
              <span className="scope-hint">{matchCount} matches — keep typing to narrow</span>
            )}
          </div>
        )}
      </div>
      {scope.length > 0 && (
        <button className="scope-clear" onClick={() => onScope([])}>clear</button>
      )}
      {hasVariants && (
        <div className="scope-variant">
          <SearchSelect
            label="Weapon"
            value={variantId === null ? "" : String(variantId)}
            options={variantOptions}
            placeholder="All weapons"
            onChange={(v) => {
              // Unlabeled fingerprints without an identity row (shouldn't
              // happen — ingest auto-creates them) can't filter server-side.
              if (v !== "" && (v.startsWith("fp:") || Number.isNaN(Number(v)))) return;
              onVariant(v === "" ? null : Number(v));
            }}
          />
          <button className="scope-edit" title="Name your weapons"
            onClick={() => setVariantMenu(!variantMenu)}>✎</button>
          {variantMenu && (
            <div className="scope-variant-menu">
              <WeaponVariantManager playerId={scope[0]}
                onChanged={() => { apiInvalidate(); loadVariants(scope[0]); }} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
