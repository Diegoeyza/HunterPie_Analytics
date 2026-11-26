"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiSend, type UpdateInfo } from "../lib/api";
import { useToast } from "./Toast";
import { useT } from "../lib/i18n";

/** Header pill: shows when a newer release exists and installs it in place.
 *  The backend downloads + verifies the installer, launches it silently and
 *  quits, so the app reopens updated. Nothing here runs unless enabled. */
export default function UpdatePill({ enabled }: { enabled: boolean }) {
  const [info, setInfo] = useState<UpdateInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const { t } = useT();

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
    if (!info.installable) {
      // Linux (or any non-Windows build): no silent installer — hand the
      // download to the system browser.
      try {
        await apiSend<{ status: string }>("POST", "/update/open");
        toast.push(t("settings.update.opening", { version: info.latest }));
      } catch (e) {
        toast.push(e instanceof Error ? e.message : t("settings.update.openFailed"), true);
      } finally {
        setBusy(false);
      }
      return;
    }
    const mb = info.size ? Math.round(info.size / 1048576) : null;
    toast.push(mb
      ? t("settings.update.downloadingSize", { version: info.latest, mb })
      : t("settings.update.downloading", { version: info.latest }));
    try {
      await apiSend<{ status: string }>("POST", "/update/run");
      toast.push(t("settings.update.installing"));
    } catch (e) {
      setBusy(false);
      toast.push(e instanceof Error ? e.message : t("settings.update.failed"), true);
    }
  }, [info, toast]);

  if (!enabled || !info?.update_available || !info.latest) return null;
  return (
    <button type="button" className="update-pill" onClick={install} disabled={busy}
      title={info.installable
        ? t("settings.update.titleInstall", { version: info.latest })
        : t("settings.update.titleDownload", { version: info.latest })}>
      {busy ? t("settings.update.updating") : info.installable
        ? t("settings.update.availableInstall", { version: info.latest })
        : t("settings.update.availableDownload", { version: info.latest })}
    </button>
  );
}
