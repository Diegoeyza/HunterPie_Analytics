"use client";

import { useState } from "react";
import { apiGet, apiSend, type Health } from "../lib/api";

interface ImportResult {
  scanned: number;
  imported: number;
  imported_ids: number[];
  duplicates: number;
  errors: { file: string; error: string }[];
}

export default function ImportButton({ onImported }: { onImported: (h: Health) => void }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  const run = async () => {
    setBusy(true);
    setMsg(null);
    setIsError(false);
    try {
      const r = await apiSend<ImportResult>("POST", "/import");
      const h = await apiGet<Health>("/health");
      onImported(h);
      if (r.errors.length > 0) {
        setIsError(true);
        setMsg(`${r.errors.length} file(s) failed (first: ${r.errors[0].file}) — ${r.imported} new hunt(s)`);
      } else if (r.imported > 0) {
        setMsg(`Imported ${r.imported} new hunt${r.imported === 1 ? "" : "s"} — refreshing…`);
        setTimeout(() => window.location.reload(), 2000);
      } else {
        setMsg(`Up to date — ${r.scanned} files, nothing new`);
      }
    } catch (e) {
      setIsError(true);
      setMsg(e instanceof Error ? e.message : "Import failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <span className="import-wrap">
      <button type="button" className="import-button" onClick={run} disabled={busy}>
        {busy ? "Importing…" : "Import hunts"}
      </button>
      {msg && <span className={`status-text ${isError ? "error" : ""}`}>{msg}</span>}
    </span>
  );
}
