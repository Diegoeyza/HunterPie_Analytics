"use client";

import { useEffect, useState } from "react";
import { useT } from "@/lib/i18n";
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
  const { t } = useT();
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
      <h3>{t("scope.nameWeapons")}</h3>
      <p className="scope-hint">
        {t("scope.nameWeaponsHint")}
      </p>
      {data.variants.map((v) => {
        const key = String(v.id);
        const dirty = (drafts[key] ?? "") !== (v.label ?? "");
        return (
          <div key={key} className="variant-row">
            <span className="variant-stats" title={`${t("unit.raw")} ${v.raw} · ${t("unit.element")} ${v.element} · ${t("unit.affinity")} ${v.affinity}`}>
              {variantLabel({ ...v, label: null })}
            </span>
            <span className="scope-hint">{t(v.hunts === 1 ? "scope.hunts.one" : "scope.hunts.other", { n: v.hunts })}</span>
            <input
              className="variant-input"
              placeholder={t("scope.variantPlaceholder")}
              value={drafts[key] ?? ""}
              onChange={(e) => setDrafts((d) => ({ ...d, [key]: e.target.value }))}
              onKeyDown={(e) => { if (e.key === "Enter" && dirty) void save(v); }}
            />
            <button disabled={!dirty || saving === key} onClick={() => void save(v)}>
              {saving === key ? "…" : v.label ? t("scope.rename") : t("scope.nameIt")}
            </button>
          </div>
        );
      })}
      {data.unknown_hunts > 0 && (
        <p className="scope-hint">
          {t(data.unknown_hunts === 1 ? "scope.unknownHunts.one" : "scope.unknownHunts.other", { n: data.unknown_hunts })}
        </p>
      )}
    </div>
  );
}
