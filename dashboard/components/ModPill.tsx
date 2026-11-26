"use client";

import { useEffect, useState } from "react";
import type { ModStatus } from "../lib/api";
import Modal from "./Modal";
import { useToast } from "./Toast";
import { useT } from "../lib/i18n";

const SEEN_KEY = "hp.modNoticeSeen";

/** Header pill + one-time toast when the newest mod dump is older than the
 *  HuntDumper bundled with this app (i.e. after an app update). */
export default function ModPill({ mod }: { mod?: ModStatus }) {
  const [open, setOpen] = useState(false);
  const toast = useToast();
  const { t } = useT();

  useEffect(() => {
    if (!mod?.outdated || !mod.expected || !mod.installed) return;
    const key = `${mod.expected}|${mod.installed}`;
    let seen = "";
    try { seen = localStorage.getItem(SEEN_KEY) ?? ""; } catch { /* private mode */ }
    if (seen === key) return;
    try { localStorage.setItem(SEEN_KEY, key); } catch { /* ignore */ }
    toast.push(t("settings.mod.toast", { version: mod.expected }));
  }, [mod, toast]);

  if (!mod?.outdated || !mod.expected || !mod.installed) return null;

  return (
    <>
      <button type="button" className="mod-pill" onClick={() => setOpen(true)}
        title={t("settings.mod.title", { expected: mod.expected, installed: mod.installed })}>
        {t("settings.mod.pill", { installed: mod.installed })}
      </button>
      {open && (
        <Modal label={t("settings.mod.modalLabel")} onClose={() => setOpen(false)}>
          <div className="modal-head">
            <h2>{t("settings.mod.heading")}</h2>
            <button type="button" className="modal-close" aria-label={t("common.close")}
              onClick={() => setOpen(false)}>✕</button>
          </div>
          <p>
            {t("settings.mod.bodyBefore")} <strong>v{mod.expected}</strong>
            {t("settings.mod.bodyMiddle")} <strong>v{mod.installed}</strong>{t("settings.mod.bodyEnd")}
          </p>
          <p>
            {t("settings.mod.copyBefore")} <code>HuntDumper\hunt_dumper.lua</code>
            {" "}{t("settings.mod.copyAfter")}
          </p>
          <pre>&lt;game&gt;\reframework\autorun\hunt_dumper.lua</pre>
          <p>
            {t("settings.mod.overwrite")}
          </p>
          <p>
            <a href="https://github.com/Diegoeyza/HunterPie_Analytics/releases/latest"
              target="_blank" rel="noreferrer">{t("settings.mod.download")}</a>
          </p>
        </Modal>
      )}
    </>
  );
}
