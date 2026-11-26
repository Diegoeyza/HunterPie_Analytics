"use client";

import Modal from "./Modal";
import { noteFor, RELEASES_URL } from "../lib/changelog";
import { useT } from "../lib/i18n";

/** One-time "what's new" dialog after an update, re-openable from Settings.
 *  Whether it auto-opens is decided in app/page.tsx, which owns the
 *  seen-version bookkeeping. */
export default function WhatsNew({ appVersion, open, onClose }: {
  appVersion?: string;
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useT();
  const note = noteFor(appVersion);
  if (!open || !note) return null;
  return (
    <Modal label={t("settings.whatsNew")} onClose={onClose}>
      <div className="modal-head">
        <h2>{t("settings.whatsNew.heading", { version: note.version })}</h2>
        <button type="button" className="import-button" onClick={onClose}>
          {t("common.close")}
        </button>
      </div>
      <div className="whatsnew">
        <p className="whatsnew-title">{t(note.title)}</p>
        <ul>
          {note.bullets.map((b) => <li key={b}>{t(b)}</li>)}
        </ul>
        <p className="settings-hint">
          <a href={RELEASES_URL} target="_blank" rel="noreferrer">
            {t("settings.whatsNew.releaseNotes")}
          </a>
        </p>
      </div>
    </Modal>
  );
}
