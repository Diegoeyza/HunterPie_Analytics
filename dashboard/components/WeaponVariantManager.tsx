"use client";

import { useEffect, useState } from "react";
import {
  apiGet, apiPatch, variantLabel,
  type PlayerVariants, type VariantOption,
} from "../lib/api";

interface Props {
  playerId: number;
  onChanged: () => void;
}

/** Label-once manager: name each gear fingerprint a single hunter has used.
 *  Rendered inside the scope bar's naming menu (opened via the edit
 *  button next to the weapon selector). */
export default function WeaponVariantManager({ playerId, onChanged }: Props) {
  const [data, setData] = useState<PlayerVariants | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    apiGet<PlayerVariants>(`/players/${playerId}/variants`)
      .then((d) => {
        setData(d);
        setDrafts(Object.fromEntries(
          d.variants.map((v) => [String(v.id), v.label ?? ""])
        ));
      })
      .catch((e: Error) => setError(e.message));
  };
  useEffect(refresh, [playerId]);

  if (error) return null;
  if (data === null) return null;
  if (data.variants.length === 0) return null;

  const save = async (v: VariantOption) => {
    if (v.id === null) return;
    const key = String(v.id);
    setSaving(key);
    setError(null);
    try {
      await apiPatch<{ id: number; label: string | null }>(
        `/weapon-identities/${v.id}`, { label: drafts[key] ?? "" });
      refresh();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "save failed");
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="card variant-manager">
      <h3>Name your weapons</h3>
      <p className="scope-hint">
        Each distinct weapon you have used is listed once — give it a name
        and every hunt with those stats resolves to it.
      </p>
      {data.variants.map((v) => {
        const key = String(v.id);
        const dirty = (drafts[key] ?? "") !== (v.label ?? "");
        return (
          <div key={key} className="variant-row">
            <span className="variant-stats" title={`raw ${v.raw} · element ${v.element} · affinity ${v.affinity}`}>
              {variantLabel({ ...v, label: null })}
            </span>
            <span className="scope-hint">{v.hunts} hunt{v.hunts === 1 ? "" : "s"}</span>
            <input
              className="variant-input"
              placeholder='e.g. "Artian Horn III"'
              value={drafts[key] ?? ""}
              onChange={(e) => setDrafts((d) => ({ ...d, [key]: e.target.value }))}
              onKeyDown={(e) => { if (e.key === "Enter" && dirty) void save(v); }}
            />
            <button disabled={!dirty || saving === key} onClick={() => void save(v)}>
              {saving === key ? "…" : v.label ? "Rename" : "Name it"}
            </button>
          </div>
        );
      })}
      {data.unknown_hunts > 0 && (
        <p className="scope-hint">
          + {data.unknown_hunts} hunt{data.unknown_hunts === 1 ? "" : "s"} from
          before weapon tracking (shown as Unknown).
        </p>
      )}
    </div>
  );
}
