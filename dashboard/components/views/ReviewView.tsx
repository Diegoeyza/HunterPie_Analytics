"use client";

import { useState } from "react";
import { apiSend, type AliasItem } from "../../lib/api";
import { apiInvalidate } from "../../lib/api";
import { fmtDate } from "../../lib/format";
import { ApiState, useApi } from "../../lib/useApi";
import EmptyState from "../EmptyState";
import { useToast } from "../Toast";

/** Rename-review queue: ingest flags case-variant sightings ("Diego" vs
 *  "DIEGO") instead of merging them. Merge reassigns every hunt row to
 *  the target hunter; Dismiss keeps them separate explicitly.
 */
export default function ReviewView() {
  const { data, error, loading, refetch } = useApi<{ aliases: AliasItem[] }>("/players/aliases");
  const [busy, setBusy] = useState<number | null>(null);
  const toast = useToast();
  const rows = data?.aliases ?? null;

  const act = async (id: number, kind: "merge" | "dismiss", label: string) => {
    setBusy(id);
    try {
      const res = kind === "merge"
        ? await apiSend<{ merged: string; into: string; hunts: number }>(
          "POST", `/players/aliases/${id}/merge`)
        : await apiSend("DELETE", `/players/aliases/${id}`);
      if (kind === "merge") {
        toast.push(`Merged ${(res as { merged: string }).merged} into ${(res as { into: string }).into} (${(res as { hunts: number }).hunts} hunts)`);
      } else {
        toast.push(`Kept ${label} as a separate hunter`);
      }
      apiInvalidate();
      refetch();
    } catch (e) {
      toast.push(e instanceof Error ? e.message : `${kind} failed`, true);
    } finally {
      setBusy(null);
    }
  };

  if (error || loading || !rows) return <ApiState error={error} loading={loading} />;
  if (rows.length === 0) {
    return (
      <EmptyState what="rename reviews">
        <p>No flagged renames — every hunter name resolves cleanly.</p>
      </EmptyState>
    );
  }

  return (
    <div className="card">
      <h2>Rename reviews ({rows.length})</h2>
      <p className="blurb">
        Ingest flagged these as possible renames (same name, different case).
        Nothing was merged — pick per row.
      </p>
      <div className="hunt-list">
        {rows.map((a) => (
          <div key={a.id} className="hunt-row">
            <span className="hunt-main">
              <strong>{a.alias}</strong>
              <span className="hunt-sub">
                resembles <strong>{a.player}</strong> · seen {fmtDate(a.created_at)}
              </span>
            </span>
            <button type="button" className="row-action" disabled={busy === a.id}
              title={`Move all of ${a.alias}'s hunts to ${a.player}`}
              onClick={() => act(a.id, "merge", a.alias)}>
              {busy === a.id ? "…" : "Merge"}
            </button>
            <button type="button" className="row-action" disabled={busy === a.id}
              title={`Keep ${a.alias} as a separate hunter`}
              onClick={() => act(a.id, "dismiss", a.alias)}>
              {busy === a.id ? "…" : "Keep separate"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
