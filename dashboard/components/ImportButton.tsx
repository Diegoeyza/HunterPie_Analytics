"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiInvalidate, apiSend, type ImportJobStatus } from "../lib/api";
import { useToast } from "./Toast";
import { useT } from "@/lib/i18n";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Header import button: background HuntExports import with progress.
 *  No page reloads — cache invalidation + onImported refresh every view.
 *  Supports cancel (server-side) and surfaces per-file warnings.
 */
export default function ImportButton({ onImported }: { onImported: () => void }) {
  const [busy, setBusy] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ImportJobStatus | null>(null);
  const cancelled = useRef(false);
  const toast = useToast();
  const { t } = useT();

  useEffect(() => () => { cancelled.current = true; }, []);

  const finish = (st: ImportJobStatus) => {
    apiInvalidate();
    onImported();
    if (st.state === "cancelled") {
      toast.push(t(st.imported === 1 ? "table.import.cancelled.one" : "table.import.cancelled.other", {
        count: st.imported,
      }), true);
    } else if (st.state === "error") {
      toast.push(t("table.import.failed", {
        error: st.error ?? t("table.import.unknownError"),
      }), true);
    } else if (st.errors.length > 0) {
      toast.push(t(st.errors.length === 1 ? "table.import.failedFiles.one" : "table.import.failedFiles.other", {
        count: st.errors.length, file: st.errors[0].file, imported: st.imported,
      }), true);
    } else if (st.imported === 0) {
      toast.push(t("table.import.upToDate", {
        scanned: st.scanned, skipped: st.skipped_manifest,
      }));
    } else if (st.warnings.length > 0) {
      const notes = st.warnings.reduce((a, w) => a + w.warnings.length, 0);
      toast.push(t(st.imported === 1 ? "table.import.importedNotes.one" : "table.import.importedNotes.other", {
        count: st.imported, notes,
      }));
    } else if (st.imported > 0) {
      toast.push(t(st.imported === 1 ? "table.import.imported.one" : "table.import.imported.other", {
        count: st.imported,
      }));
    } else {
      toast.push(t("table.import.upToDate", {
        scanned: st.scanned, skipped: st.skipped_manifest,
      }));
    }
  };

  const run = async (force: boolean) => {
    setBusy(true);
    setProgress(null);
    try {
      const { job_id } = await apiSend<{ job_id: string }>(
        "POST", force ? "/import?force=1" : "/import");
      setJobId(job_id);
      for (;;) {
        await sleep(500);
        if (cancelled.current) return;
        let st: ImportJobStatus;
        try {
          st = await apiGet<ImportJobStatus>("/import/status", { job_id });
        } catch (e) {
          if (cancelled.current) return;
          throw e;
        }
        if (cancelled.current) return;
        setProgress(st);
        if (st.state !== "running") {
          finish(st);
          break;
        }
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : t("table.import.failedDefault");
      // 409 = another import already running (single-flight).
      toast.push(msg.includes("409") ? t("table.import.alreadyRunning") : msg, true);
    } finally {
      setBusy(false);
      setJobId(null);
    }
  };

  const cancel = async () => {
    if (!jobId) return;
    try {
      await apiSend("POST", `/import/cancel?job_id=${jobId}`);
    } catch {
      /* the poll loop surfaces the terminal state */
    }
  };

  const pct = progress && progress.total > 0
    ? Math.round((progress.scanned / progress.total) * 100)
    : null;

  return (
    <span className="import-wrap">
      <button type="button" className="import-button" onClick={() => run(false)} disabled={busy}>
        {busy ? t("table.import.busy") : t("table.import.button")}
      </button>
      <button
        type="button"
        className="import-button import-button--ghost"
        title={t("table.import.fullRecheckTitle")}
        onClick={() => run(true)}
        disabled={busy}
      >
        {t("table.import.fullRecheck")}
      </button>
      {busy && (
        <button type="button" className="import-button import-button--ghost"
          onClick={cancel} title={t("table.import.cancelTitle")}>
          {t("common.cancel")}
        </button>
      )}
      {busy && progress && (
        <span className="import-progress" role="status" aria-label={t("table.import.progress")}>
          <progress value={progress.scanned} max={Math.max(progress.total, 1)} />
          <span className="status-text">
            {progress.scanned}/{progress.total}{pct !== null ? ` (${pct}%)` : ""}
            {` · ${t("table.import.progressDetail", {
              imported: progress.imported, duplicates: progress.duplicates,
            })}`}
          </span>
        </span>
      )}
    </span>
  );
}
