"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiSend, type UpdateInfo } from "../lib/api";
import { useToast } from "./Toast";

/** Header pill: shows when a newer release exists and installs it in place.
 *  The backend downloads + verifies the installer, launches it silently and
 *  quits, so the app reopens updated. Nothing here runs unless enabled. */
export default function UpdatePill({ enabled }: { enabled: boolean }) {
  const [info, setInfo] = useState<UpdateInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  useEffect(() => {
    if (!enabled) {
      setInfo(null);
      return;
    }
    let alive = true;
    apiGet<UpdateInfo>("/update")
      .then((d) => { if (alive) setInfo(d); })
      .catch(() => { /* offline: stay silent */ });
    return () => { alive = false; };
  }, [enabled]);

  const install = useCallback(async () => {
    if (!info?.latest) return;
    setBusy(true);
    const mb = info.size ? Math.round(info.size / 1048576) : null;
    toast.push(`Downloading v${info.latest}${mb ? ` (~${mb} MB)` : ""}…`);
    try {
      await apiSend<{ status: string }>("POST", "/update/run");
      toast.push("Installing — the app will close and reopen updated.");
    } catch (e) {
      setBusy(false);
      toast.push(e instanceof Error ? e.message : "Update failed", true);
    }
  }, [info, toast]);

  if (!enabled || !info?.update_available || !info.latest) return null;
  return (
    <button type="button" className="update-pill" onClick={install} disabled={busy}
      title={`Update to v${info.latest}`}>
      {busy ? "Updating…" : `↑ v${info.latest} available`}
    </button>
  );
}
