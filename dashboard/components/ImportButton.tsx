"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiInvalidate, apiSend, type ImportJobStatus } from "../lib/api";
import { useToast } from "./Toast";

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

  useEffect(() => () => { cancelled.current = true; }, []);

  const finish = (st: ImportJobStatus) => {
    apiInvalidate();
    onImported();
    if (st.state === "cancelled") {
      toast.push(`Import cancelled — ${st.imported} new hunt(s) kept`, true);
    } else if (st.state === "error") {
      toast.push(`Import failed: ${st.error ?? "unknown error"}`, true);
    } else if (st.errors.length > 0) {
      toast.push(`${st.errors.length} file(s) failed (first: ${st.errors[0].file}) — ${st.imported} new`, true);
    } else if (st.warnings.length > 0) {
      const n = st.warnings.reduce((a, w) => a + w.warnings.length, 0);
      toast.push(`Imported ${st.imported} new hunt(s) · ${n} warning(s) — see Review tab`);
    } else if (st.imported > 0) {
      toast.push(`Imported ${st.imported} new hunt${st.imported === 1 ? "" : "s"}`);
    } else {
      toast.push(`Up to date — ${st.scanned} files (${st.skipped_manifest} skipped), nothing new`);
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
      const msg = e instanceof Error ? e.message : "Import failed";
      // 409 = another import already running (single-flight).
      toast.push(msg.includes("409") ? "An import is already running" : msg, true);
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
        {busy ? "Importing…" : "Import hunts"}
      </button>
      <button
        type="button"
        className="import-button import-button--ghost"
        title="Ignore the skip manifest and recheck every file (e.g. after deleting hunts)"
        onClick={() => run(true)}
        disabled={busy}
      >
        Full recheck
      </button>
      {busy && (
        <button type="button" className="import-button import-button--ghost"
          onClick={cancel} title="Stop after the current file">
          Cancel
        </button>
      )}
      {busy && progress && (
        <span className="import-progress" role="status" aria-label="Import progress">
          <progress value={progress.scanned} max={Math.max(progress.total, 1)} />
          <span className="status-text">
            {progress.scanned}/{progress.total}{pct !== null ? ` (${pct}%)` : ""}
            {` · ${progress.imported} new · ${progress.duplicates} dupes`}
          </span>
        </span>
      )}
    </span>
  );
}
