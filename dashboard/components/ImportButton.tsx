"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiSend, type Health } from "../lib/api";

interface ImportJobStatus {
  job_id: string;
  state: "running" | "done" | "error";
  total: number;
  scanned: number;
  imported: number;
  duplicates: number;
  skipped_manifest: number;
  imported_ids: number[];
  errors: { file: string; error: string }[];
  error: string | null;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export default function ImportButton({ onImported }: { onImported: (h: Health) => void }) {
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<ImportJobStatus | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);
  const cancelled = useRef(false);

  useEffect(() => () => { cancelled.current = true; }, []);

  const finish = async (st: ImportJobStatus) => {
    const h = await apiGet<Health>("/health");
    onImported(h);
    if (st.state === "error") {
      setIsError(true);
      setMsg(`Import failed: ${st.error ?? "unknown error"}`);
    } else if (st.errors.length > 0) {
      setIsError(true);
      setMsg(`${st.errors.length} file(s) failed (first: ${st.errors[0].file}) — ${st.imported} new hunt(s)`);
    } else if (st.imported > 0) {
      setMsg(`Imported ${st.imported} new hunt${st.imported === 1 ? "" : "s"} — refreshing…`);
      setTimeout(() => window.location.reload(), 2000);
    } else {
      setMsg(`Up to date — ${st.scanned} files (${st.skipped_manifest} skipped), nothing new`);
    }
  };

  const run = async (force: boolean) => {
    setBusy(true);
    setProgress(null);
    setMsg(null);
    setIsError(false);
    try {
      const { job_id } = await apiSend<{ job_id: string }>(
        "POST", force ? "/import?force=1" : "/import");
      for (;;) {
        await sleep(500);
        if (cancelled.current) return;
        const st = await apiGet<ImportJobStatus>("/import/status", { job_id });
        if (cancelled.current) return;
        setProgress(st);
        if (st.state !== "running") {
          await finish(st);
          break;
        }
      }
    } catch (e) {
      setIsError(true);
      setMsg(e instanceof Error ? e.message : "Import failed");
    } finally {
      setBusy(false);
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
      {busy && progress && (
        <span className="import-progress" role="status" aria-label="Import progress">
          <progress value={progress.scanned} max={Math.max(progress.total, 1)} />
          <span className="status-text">
            {progress.scanned}/{progress.total}{pct !== null ? ` (${pct}%)` : ""}
            {` · ${progress.imported} new · ${progress.duplicates} dupes`}
          </span>
        </span>
      )}
      {msg && <span className={`status-text ${isError ? "error" : ""}`}>{msg}</span>}
    </span>
  );
}
