"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPatch, type HuntSummary } from "../lib/api";
import { fmtTime } from "../lib/format";

/** Header-level hunt manager: searchable list of every hunt with
 *  ignore/restore. Closes with a refresh when anything changed. */
export default function HuntsManager() {
  const [open, setOpen] = useState(false);
  const [hunts, setHunts] = useState<HuntSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [dirty, setDirty] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    if (!open) return;
    setHunts(null);
    setError(null);
    setQ("");
    setDirty(false);
    apiGet<{ hunts: HuntSummary[] }>("/hunts", { limit: 2000, include_ignored: 1 })
      .then((d) => setHunts(d.hunts))
      .catch((e: Error) => setError(e.message));
  }, [open ]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return hunts ?? [];
    return (hunts ?? []).filter((h) =>
      String(h.id).includes(needle) ||
      h.monster.toLowerCase().includes(needle) ||
      h.started_at.slice(0, 10).includes(needle));
  }, [hunts, q]);

  const close = () => {
    setOpen(false);
    if (dirty) window.location.reload();
  };

  const toggle = async (h: HuntSummary) => {
    setBusyId(h.id);
    try {
      const res = await apiPatch<{ id: number; ignored: boolean }>(
        `/hunts/${h.id}/ignore`, { ignored: !h.ignored });
      setHunts((hs) => (hs ?? []).map((x) =>
        x.id === h.id ? { ...x, ignored: res.ignored } : x));
      setDirty(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Toggle failed");
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
        <div className="modal-backdrop" onClick={close}>
          <div className="modal" onClick={(e) => e.stopPropagation()}
            role="dialog" aria-modal="true" aria-label="Manage hunts">
            <div className="modal-head">
              <h2>All hunts{hunts ? ` (${hunts.length})` : ""}</h2>
              <button type="button" className="import-button" onClick={close}>
                {dirty ? "Close & refresh" : "Close"}
              </button>
            </div>
            <input
              className="modal-search"
              autoFocus
              placeholder="Search by monster, #id, or date…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
            {error && <p className="error">{error}</p>}
            {!hunts && !error && <p>Loading hunts…</p>}
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
          </div>
        </div>
      )}
    </>
  );
}
