"use client";

import { useEffect, useMemo, useState } from "react";
import { apiInvalidate, apiPatch, apiSend, type HuntSummary } from "../lib/api";
import { fmtClearTime, fmtDate, fmtDateTime } from "../lib/format";
import { ApiState, useApi } from "../lib/useApi";
import Modal from "./Modal";
import { useToast } from "./Toast";
import { useT } from "@/lib/i18n";
import { monsterName } from "@/lib/names";

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
  const { t, locale } = useT();

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
      monsterName(h.monster, h.monster_id).toLowerCase().includes(needle) ||
      fmtDate(h.started_at).includes(needle));
  }, [hunts, q, locale]);

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
      toast.push(e instanceof Error ? e.message : t("table.hunts.toggleFailed"), true);
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (h: HuntSummary) => {
    setBusyId(h.id);
    setConfirmId(null);
    try {
      await apiSend<{ id: number; deleted: boolean }>("DELETE", `/hunts/${h.id}`);
      toast.push(t("table.hunts.deletedToast", { id: h.id }));
      apiInvalidate();
      refetch();
    } catch (e) {
      toast.push(e instanceof Error ? e.message : t("table.hunts.deleteFailed"), true);
    } finally {
      setBusyId(null);
    }
  };

  const restore = async (h: HuntSummary) => {
    setBusyId(h.id);
    try {
      await apiSend<{ id: number; deleted: boolean }>("POST", `/hunts/${h.id}/restore`);
      toast.push(t("table.hunts.restoredToast", { id: h.id }));
      apiInvalidate();
      refetch();
    } catch (e) {
      toast.push(e instanceof Error ? e.message : t("table.hunts.restoreFailed"), true);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      <button type="button" className="import-button" onClick={() => setOpen(true)}>
        {t("table.hunts.open")}
      </button>
      {open && (
        <Modal label={t("table.hunts.manageLabel")} onClose={() => setOpen(false)}>
          <div className="modal-head">
            <h2>{t("table.hunts.title")}{hunts ? ` (${hunts.length})` : ""}</h2>
            <button type="button" className="import-button" onClick={() => { setOpen(false); refetch(); }}>
              {t("common.close")}
            </button>
          </div>
          <input
            className="modal-search"
            autoFocus
            placeholder={t("table.hunts.search")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <label className="hunt-filter">
            <input type="checkbox" checked={showDeleted}
              onChange={(e) => setShowDeleted(e.target.checked)} />
            <span>{t("table.hunts.showDeleted")}</span>
          </label>
          {confirmHunt && (
            <div className="confirm-bar" role="alertdialog" aria-label={t("table.hunts.confirmLabel")}>
              <span>
                {t("table.hunts.confirmBefore")}{" "}
                <b>#{confirmHunt.id} {monsterName(confirmHunt.monster, confirmHunt.monster_id)}</b>
                {t("table.hunts.confirmAfter")}
              </span>
              <button type="button" className="row-action"
                onClick={() => setConfirmId(null)}>
                {t("common.cancel")}
              </button>
              <button type="button" className="row-action danger"
                disabled={busyId === confirmHunt.id}
                onClick={() => remove(confirmHunt)}>
                {busyId === confirmHunt.id ? "…" : t("table.hunts.delete")}
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
                    <strong>{monsterName(h.monster, h.monster_id)}</strong>
                    {h.quest_stars != null && <span> {h.quest_stars}★</span>}
                    <span className="hunt-sub">
                      {fmtDateTime(h.started_at)} · {t("table.hunts.players", { count: h.players })} ·{" "}
                      {h.clear_s != null ? fmtClearTime(h.clear_s) : "—"}{" "}
                      · {h.cleared ? t("table.hunts.cleared") : t("table.hunts.failed")}
                      {h.deleted ? ` · ${t("table.hunts.deleted")}` : ""}
                    </span>
                  </span>
                  {h.deleted ? (
                    <button
                      type="button"
                      className="row-action"
                      disabled={busyId === h.id}
                      title={t("table.hunts.restoreTitle", { id: h.id })}
                      onClick={() => restore(h)}
                    >
                      {busyId === h.id ? "…" : t("table.hunts.restore")}
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="row-action"
                        disabled={busyId === h.id}
                        title={h.ignored
                          ? t("table.hunts.restoreIgnoredTitle", { id: h.id })
                          : t("table.hunts.ignoreTitle", { id: h.id })}
                        onClick={() => toggle(h)}
                      >
                        {busyId === h.id ? "…" : h.ignored ? t("table.hunts.restore") : t("table.hunts.ignore")}
                      </button>
                      <button
                        type="button"
                        className="row-action danger"
                        disabled={busyId === h.id}
                        title={t("table.hunts.deleteTitle", { id: h.id })}
                        onClick={() => setConfirmId(h.id)}
                      >
                        {t("table.hunts.delete")}
                      </button>
                    </>
                  )}
                </div>
              ))}
              {filtered.length === 0 && <p className="hunt-empty">{t("table.hunts.noMatch")}</p>}
            </div>
          )}
        </Modal>
      )}
    </>
  );
}
