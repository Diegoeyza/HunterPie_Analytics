"use client";

import Modal from "./Modal";
import { noteFor, RELEASES_URL } from "../lib/changelog";

/** One-time "what's new" dialog after an update, re-openable from Settings.
 *  Whether it auto-opens is decided in app/page.tsx, which owns the
 *  seen-version bookkeeping. */
export default function WhatsNew({ appVersion, open, onClose }: {
  appVersion?: string;
  open: boolean;
  onClose: () => void;
}) {
  const note = noteFor(appVersion);
  if (!open || !note) return null;
  return (
    <Modal label="What's new" onClose={onClose}>
      <div className="modal-head">
        <h2>What&apos;s new in v{note.version}</h2>
        <button type="button" className="import-button" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="whatsnew">
        <p className="whatsnew-title">{note.title}</p>
        <ul>
          {note.bullets.map((b) => <li key={b}>{b}</li>)}
        </ul>
        <p className="settings-hint">
          <a href={RELEASES_URL} target="_blank" rel="noreferrer">
            Full release notes on GitHub
          </a>
        </p>
      </div>
    </Modal>
  );
}
