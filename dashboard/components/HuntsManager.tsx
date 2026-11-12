"use client";

import { useEffect, useMemo, useState } from "react";
import { apiInvalidate, apiPatch, apiSend, type HuntSummary } from "../lib/api";
import { fmtClearTime, fmtDate, fmtDateTime } from "../lib/format";
import { ApiState, useApi } from "../lib/useApi";
import Modal from "./Modal";
import { useToast } from "./Toast";

/** Header-level hunt manager: searchable list of every hunt with
 *  ignore/restore, delete (soft, restorable via "show deleted") and a
 *  destructive inline confirmation. Mutations invalidate the cached API
 *  data so the tabs update without a reload. */
export default function HuntsManager() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [showDeleted, setShowDeleted] = useState(false);
  const [overrides, setOverrides] = useState<Map<number, boolean>>(new Map());
  const toast = useToast();

  const { data, error, loading, refetch } = useApi<{ hunts: HuntSummary[] }>(
    "/hunts", open ? {
      limit: 2000, include_ignored: 1,
      ...(showDeleted ? { include_deleted: 1 } : {}),
    } : null);
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
      setConfirmId(null);
    }
  }, [open ]);

  // Drop a pending confirmation if its hunt vanished (deleted from another
  // tab or hidden by a refetch).
  useEffect(() => {
    if (confirmId != null && hunts && !hunts.some((h) => h.id === confirmId)) {
      setConfirmId(null);
    }
  }, [confirmId, hunts]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return hunts ?? [];
    return (hunts ?? []).filter((h) =>
      String(h.id).includes(needle) ||
      h.monster.toLowerCase().includes(needle) ||
      fmtDate(h.started_at).includes(needle));
  }, [hunts, q]);

  const confirmHunt = confirmId != null
    ? hunts?.find((h) => h.id === confirmId) ?? null
    : null;

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

  const remove = async (h: HuntSummary) => {
    setBusyId(h.id);
    setConfirmId(null);
    try {
      await apiSend<{ id: number; deleted: boolean }>("DELETE", `/hunts/${h.id}`);
      toast.push(`Hunt #${h.id} deleted.`);
      apiInvalidate();
      refetch();
    } catch (e) {
      toast.push(e instanceof Error ? e.message : "Delete failed", true);
    } finally {
      setBusyId(null);
    }
  };

  const restore = async (h: HuntSummary) => {
    setBusyId(h.id);
    try {
      await apiSend<{ id: number; deleted: boolean }>("POST", `/hunts/${h.id}/restore`);
      toast.push(`Hunt #${h.id} restored.`);
      apiInvalidate();
      refetch();
    } catch (e) {
      toast.push(e instanceof Error ? e.message : "Restore failed", true);
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
          <label className="hunt-filter">
            <input type="checkbox" checked={showDeleted}
              onChange={(e) => setShowDeleted(e.target.checked)} />
            <span>Show deleted</span>
          </label>
          {confirmHunt && (
            <div className="confirm-bar" role="alertdialog" aria-label="Confirm delete">
              <span>
                Delete hunt <b>#{confirmHunt.id} {confirmHunt.monster}</b>? It is
                removed from every stat and from this list, and a re-import
                won&apos;t bring it back.
              </span>
              <button type="button" className="row-action"
                onClick={() => setConfirmId(null)}>
                Cancel
              </button>
              <button type="button" className="row-action danger"
                disabled={busyId === confirmHunt.id}
                onClick={() => remove(confirmHunt)}>
                {busyId === confirmHunt.id ? "…" : "Delete"}
              </button>
            </div>
          )}
          <ApiState error={error} loading={loading || !hunts} />
          {hunts && (
            <div className="hunt-list">
              {filtered.map((h) => (
                <div key={h.id}
                  className={`hunt-row${h.ignored ? " is-ignored" : ""}${h.deleted ? " is-deleted" : ""}`}>
                  <span className="hunt-id">#{h.id}</span>
                  <span className="hunt-main">
                    <strong>{h.monster}</strong>
                    {h.quest_stars != null && <span> {h.quest_stars}★</span>}
                    <span className="hunt-sub">
                      {fmtDateTime(h.started_at)} · {h.players}p ·{" "}
                      {h.clear_s != null ? fmtClearTime(h.clear_s) : "—"}{" "}
                      · {h.cleared ? "cleared" : "failed"}
                      {h.deleted ? " · deleted" : ""}
                    </span>
                  </span>
                  {h.deleted ? (
                    <button
                      type="button"
                      className="row-action"
                      disabled={busyId === h.id}
                      title={`Restore deleted hunt #${h.id}`}
                      onClick={() => restore(h)}
                    >
                      {busyId === h.id ? "…" : "Restore"}
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="row-action"
                        disabled={busyId === h.id}
                        title={h.ignored ? `Restore hunt #${h.id} to stats` : `Ignore hunt #${h.id} in stats`}
                        onClick={() => toggle(h)}
                      >
                        {busyId === h.id ? "…" : h.ignored ? "Restore" : "Ignore"}
                      </button>
                      <button
                        type="button"
                        className="row-action danger"
                        disabled={busyId === h.id}
                        title={`Delete hunt #${h.id} permanently`}
                        onClick={() => setConfirmId(h.id)}
                      >
                        Delete
                      </button>
                    </>
                  )}
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
