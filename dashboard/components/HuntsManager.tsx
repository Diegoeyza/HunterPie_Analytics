"use client";

import { useEffect, useMemo, useState } from "react";
import { apiInvalidate, apiPatch, type HuntSummary } from "../lib/api";
import { fmtTime } from "../lib/format";
import { ApiState, useApi } from "../lib/useApi";
import Modal from "./Modal";
import { useToast } from "./Toast";

/** Header-level hunt manager: searchable list of every hunt with
 *  ignore/restore. Mutations invalidate the API cache (no reload). */
export default function HuntsManager() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [overrides, setOverrides] = useState<Map<number, boolean>>(new Map());
  const toast = useToast();

  const { data, error, loading, refetch } = useApi<{ hunts: HuntSummary[] }>(
    "/hunts", open ? { limit: 2000, include_ignored: 1 } : null);
  const hunts = useMemo(() => {
    const list = data?.hunts ?? null;
    if (!list || overrides.size === 0) return list;
    return list.map((h) => overrides.has(h.id)
      ? { ...h, ignored: overrides.get(h.id)! } : h);
  }, [data, overrides]);

  useEffect(() => {
    if (open) {
      setQ("");
      setOverrides(new Map());
    }
  }, [open ]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return hunts ?? [];
    return (hunts ?? []).filter((h) =>
      String(h.id).includes(needle) ||
      h.monster.toLowerCase().includes(needle) ||
      h.started_at.slice(0, 10).includes(needle));
  }, [hunts, q]);

  const toggle = async (h: HuntSummary) => {
    setBusyId(h.id);
    try {
      const res = await apiPatch<{ id: number; ignored: boolean }>(
        `/hunts/${h.id}/ignore`, { ignored: !h.ignored });
      setOverrides((m) => new Map(m).set(h.id, res.ignored));
      apiInvalidate();
    } catch (e) {
      toast.push(e instanceof Error ? e.message : "Toggle failed", true);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      <button type="button" className="import-button" onClick={() => setOpen(true)}>
        Hunts
      </button>
      {open && (
        <Modal label="Manage hunts" onClose={() => setOpen(false)}>
          <div className="modal-head">
            <h2>All hunts{hunts ? ` (${hunts.length})` : ""}</h2>
            <button type="button" className="import-button" onClick={() => { setOpen(false); refetch(); }}>
              Close
            </button>
          </div>
          <input
            className="modal-search"
            autoFocus
            placeholder="Search by monster, #id, or date…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <ApiState error={error} loading={loading || !hunts} />
          {hunts && (
            <div className="hunt-list">
              {filtered.map((h) => (
                <div key={h.id} className={`hunt-row${h.ignored ? " is-ignored" : ""}`}>
                  <span className="hunt-id">#{h.id}</span>
                  <span className="hunt-main">
                    <strong>{h.monster}</strong>
                    {h.quest_stars != null && <span> {h.quest_stars}★</span>}
                    <span className="hunt-sub">
                      {h.started_at.slice(0, 10)} · {h.players}p ·{" "}
                      {h.clear_s != null ? fmtTime(h.clear_s) : "—"}{" "}
                      · {h.cleared ? "cleared" : "failed"}
                    </span>
                  </span>
                  <button
                    type="button"
                    className="row-action"
                    disabled={busyId === h.id}
                    title={h.ignored ? `Restore hunt #${h.id} to stats` : `Ignore hunt #${h.id} in stats`}
                    onClick={() => toggle(h)}
                  >
                    {busyId === h.id ? "…" : h.ignored ? "Restore" : "Ignore"}
                  </button>
                </div>
              ))}
              {filtered.length === 0 && <p className="hunt-empty">No hunts match.</p>}
            </div>
          )}
        </Modal>
      )}
    </>
  );
}
