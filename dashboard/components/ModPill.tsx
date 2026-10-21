"use client";

import { useEffect, useState } from "react";
import type { ModStatus } from "../lib/api";
import Modal from "./Modal";
import { useToast } from "./Toast";

const SEEN_KEY = "hp.modNoticeSeen";

/** Header pill + one-time toast when the newest mod dump is older than the
 *  HuntDumper bundled with this app (i.e. after an app update). */
export default function ModPill({ mod }: { mod?: ModStatus }) {
  const [open, setOpen] = useState(false);
  const toast = useToast();

  useEffect(() => {
    if (!mod?.outdated || !mod.expected || !mod.installed) return;
    const key = `${mod.expected}|${mod.installed}`;
    let seen = "";
    try { seen = localStorage.getItem(SEEN_KEY) ?? ""; } catch { /* private mode */ }
    if (seen === key) return;
    try { localStorage.setItem(SEEN_KEY, key); } catch { /* ignore */ }
    toast.push(`App updated — reinstall HuntDumper v${mod.expected} to enable party HP and quest results.`);
  }, [mod, toast]);

  if (!mod?.outdated || !mod.expected || !mod.installed) return null;

  return (
    <>
      <button type="button" className="mod-pill" onClick={() => setOpen(true)}
        title={`The app ships HuntDumper v${mod.expected}; your newest mod dump came from v${mod.installed}.`}>
        Mod v{mod.installed} → reinstall
      </button>
      {open && (
        <Modal label="Update the REFramework mod" onClose={() => setOpen(false)}>
          <div className="modal-head">
            <h2>Update the REFramework mod</h2>
            <button type="button" className="modal-close" aria-label="Close"
              onClick={() => setOpen(false)}>✕</button>
          </div>
          <p>
            This app ships HuntDumper <strong>v{mod.expected}</strong>, but the
            newest mod dump came from <strong>v{mod.installed}</strong>.
          </p>
          <p>
            Copy <code>HuntDumper\hunt_dumper.lua</code> from the app&apos;s install
            folder to:
          </p>
          <pre>&lt;game&gt;\reframework\autorun\hunt_dumper.lua</pre>
          <p>
            Overwrite the old file, then restart the game. Party HP (Survival)
            and time-up failure detection need the newer mod.
          </p>
          <p>
            <a href="https://github.com/Diegoeyza/HunterPie_Analytics/releases/latest"
              target="_blank" rel="noreferrer">Download the latest mod</a>
          </p>
        </Modal>
      )}
    </>
  );
}
