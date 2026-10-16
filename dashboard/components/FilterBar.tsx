"use client";

import { useMemo } from "react";
import SearchSelect from "./SearchSelect";
import { useFilterOptions } from "./useFilterOptions";
import type { AwardMeta, FilterOptions } from "../lib/api";

/** Shared filter selects: one options-mapping + stars-narrowing logic for
 *  every view (replaces 6 copies of the Monster/Stars pair). Views keep
 *  their own filter state; these are controlled inputs.
 */
export function MonsterSelect({ value, onChange, opts }: {
  value: string; onChange: (v: string) => void; opts?: FilterOptions | null;
}) {
  const fallback = useFilterOptions();
  const o = opts ?? fallback;
  return (
    <SearchSelect
      label="Monster"
      value={value}
      options={(o?.monsters ?? []).map((m) => ({ value: String(m.id), label: m.name }))}
      onChange={(v) => { onChange(v); }}
    />
  );
}

/** Stars dropdown narrowed to the picked monster (falls back to all). */
export function StarsSelect({ value, onChange, monster, opts }: {
  value: string; onChange: (v: string) => void; monster: string;
  opts?: FilterOptions | null;
}) {
  const fallback = useFilterOptions();
  const o = opts ?? fallback;
  const stars = monster
    ? (o?.monster_stars[Number(monster)] ?? o?.stars ?? [])
    : (o?.stars ?? []);
  return (
    <label>Stars
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All</option>
        {stars.map((s) => <option key={s} value={s}>{s}★</option>)}
      </select>
    </label>
  );
}

export function WeaponSelect({ value, onChange, opts }: {
  value: string; onChange: (v: string) => void; opts?: FilterOptions | null;
}) {
  const fallback = useFilterOptions();
  const o = opts ?? fallback;
  return (
    <SearchSelect
      label="Weapon"
      value={value}
      options={(o?.weapons ?? []).map((w) => ({ value: String(w.id), label: w.name }))}
      onChange={onChange}
    />
  );
}

/** Multi-select of highlights (awards) to show. Native <details> popover so
 *  it needs no external state; controlled by the selected id list. */
export function AwardMultiSelect({ options, value, onChange, label = "Highlights" }: {
  options: AwardMeta[]; value: number[]; onChange: (ids: number[]) => void;
  label?: string;
}) {
  if (options.length === 0) return null;
  const all = options.map((o) => o.id);
  const toggle = (id: number) =>
    onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id]);
  return (
    <details className="multiselect">
      <summary>{label} ({value.length}/{options.length})</summary>
      <div className="multiselect-menu">
        <div className="multiselect-actions">
          <button type="button" onClick={() => onChange(all)}>All</button>
          <button type="button" onClick={() => onChange([])}>None</button>
        </div>
        {options.map((o) => (
          <label key={o.id} className="multiselect-item">
            <input type="checkbox" checked={value.includes(o.id)}
              onChange={() => toggle(o.id)} />
            <span>{o.name}</span>
          </label>
        ))}
      </div>
    </details>
  );
}

export function HunterSelect({ value, onChange, opts }: {
  value: string; onChange: (v: string) => void; opts?: FilterOptions | null;
}) {
  const fallback = useFilterOptions();
  const o = opts ?? fallback;
  return (
    <SearchSelect
      label="Hunter"
      value={value}
      options={(o?.players ?? []).map((p) => ({ value: String(p.id), label: p.name }))}
      onChange={onChange}
    />
  );
}

/** Quest-group options shared by Progress (real quests collapse repeats,
 *  starless survey slots stay split by target: `391@m10` values).
 */
export function useQuestOptions(opts?: FilterOptions | null) {
  const fallback = useFilterOptions();
  const o = opts ?? fallback;
  return useMemo(() => {
    const byId = new Map<string, { id: number; mid: number; monsters: string[]; stars: number | null }>();
    for (const q of o?.quests ?? []) {
      if (q.quest_id == null) continue;
      const key = `${q.quest_id}|${q.monster}`;
      const g = byId.get(key);
      if (g) {
        if (!g.monsters.includes(q.monster)) g.monsters.push(q.monster);
      } else {
        byId.set(key, { id: q.quest_id, mid: q.monster_id, monsters: [q.monster], stars: q.stars });
      }
    }
    return [...byId.values()].map((g) => ({
      value: g.stars != null ? String(g.id) : `${g.id}@m${g.mid}`,
      label: `#${g.id} ${g.monsters.join(" + ")}${g.stars ? ` ${g.stars}★` : ""}`,
    }));
  }, [o]);
}

/** Split a survey-style quest value (`391@m10`) into [quest_id, monster_id]. */
export function splitQuestValue(quest: string): [string, string] {
  return quest.includes("@m") ? quest.split("@m") as [string, string] : [quest, ""];
}
