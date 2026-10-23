"use client";

import { useEffect, useState } from "react";
import { apiGet, apiInvalidate, apiPut, type AppSettings } from "../lib/api";
import Modal from "./Modal";
import { useToast } from "./Toast";

const THEME_KEY = "hp.theme";
type Theme = "dark" | "light";

export function loadTheme(): Theme {
  try {
    return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

/** Top-bar settings dialog: theme, DPS window, ingest folders, update check.
 *  Persists theme to localStorage and applies it to <html data-theme>. */
export default function SettingsMenu({ includeFailed, onIncludeFailed,
  checkUpdates, onCheckUpdates, appVersion }: {
  includeFailed: boolean;
  onIncludeFailed: (value: boolean) => void;
  checkUpdates: boolean;
  onCheckUpdates: (value: boolean) => void;
  appVersion?: string;
}) {
  const [theme, setTheme] = useState<Theme>("dark");
  const [open, setOpen] = useState(false);
  const [exportDirs, setExportDirs] = useState<string[]>([]);
  const [missing, setMissing] = useState<string[]>([]);
  const [detected, setDetected] = useState<AppSettings["detected"]>([]);
  const [envOverride, setEnvOverride] = useState(false);
  const [newDir, setNewDir] = useState("");
  const [dpsWindow, setDpsWindow] = useState("quest");
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  useEffect(() => {
    setTheme(loadTheme());
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch { /* private mode: theme just won't persist */ }
  }, [theme]);

  useEffect(() => {
    apiGet<AppSettings>("/settings")
      .then((s) => {
        setExportDirs(s.export_dirs);
        setMissing(s.missing);
        setDetected(s.detected);
        setEnvOverride(s.env_override);
        setDpsWindow(s.dps_window === "quest" ? "quest" : "engagement");
      })
      .catch(() => { /* settings are optional; imports still auto-detect */ });
  }, []);

  const saveSettings = async (dirs: string[], window: string) => {
    setSaving(true);
    try {
      const s = await apiPut<AppSettings>("/settings", { export_dirs: dirs, dps_window: window });
      setExportDirs(s.export_dirs);
      setMissing(s.missing);
      setDetected(s.detected);
      setEnvOverride(s.env_override);
      setDpsWindow(s.dps_window === "quest" ? "quest" : "engagement");
      setNewDir("");
      apiInvalidate();
      return true;
    } catch (e) {
      toast.push(e instanceof Error ? e.message : "Could not save settings", true);
      return false;
    } finally {
      setSaving(false);
    }
  };

  const saveDirs = async (dirs: string[]) => {
    const ok = await saveSettings(dirs, dpsWindow);
    if (ok) toast.push(missing.length > 0
      ? "Saved. That folder doesn't exist yet — it will be scanned once it does."
      : "Hunt exports folder saved");
    return ok;
  };

  const saveDpsWindow = async (window: string) => {
    setDpsWindow(window);
    const ok = await saveSettings(exportDirs, window);
    if (ok) toast.push(window === "quest"
      ? "DPS now divides by first hit → kill"
      : "DPS now divides by first → last hit");
    return ok;
  };

  const addDir = async () => {
    const value = newDir.trim();
    if (!value || saving) return;
    await saveDirs([...exportDirs, value]);
  };

  return (
    <>
      <button type="button" className="settings-open" title="Settings"
        aria-label="Settings" aria-haspopup="dialog"
        onClick={() => setOpen(true)}>⚙</button>
      {open && (
        <Modal label="Settings" onClose={() => setOpen(false)}>
          <div className="modal-head">
            <h2>Settings</h2>
            <button type="button" className="row-action"
              onClick={() => setOpen(false)}>Close</button>
          </div>
          <div className="settings-page">
            <section aria-label="Display">
              <h3>Display</h3>
              <div className="settings-row">
                <span>Theme</span>
                <div className="seg" role="group" aria-label="Theme">
                  <button type="button" className={theme === "dark" ? "on" : ""}
                    aria-pressed={theme === "dark"}
                    onClick={() => setTheme("dark")}>Dark</button>
                  <button type="button" className={theme === "light" ? "on" : ""}
                    aria-pressed={theme === "light"}
                    onClick={() => setTheme("light")}>Light</button>
                </div>
              </div>
            </section>

            <section aria-label="DPS window">
              <h3>DPS window</h3>
              <div className="settings-choices" role="radiogroup" aria-label="DPS window">
                <button type="button" role="radio"
                  aria-checked={dpsWindow === "engagement"}
                  className={dpsWindow === "engagement" ? "on" : ""}
                  disabled={saving}
                  onClick={() => saveDpsWindow("engagement")}>
                  <b>First → last hit</b>
                  <span>Your active fighting time. Late joiners are divided
                  by their own time in the fight.</span>
                </button>
                <button type="button" role="radio"
                  aria-checked={dpsWindow === "quest"}
                  className={dpsWindow === "quest" ? "on" : ""}
                  disabled={saving}
                  onClick={() => saveDpsWindow("quest")}>
                  <b>First hit → kill</b>
                  <span>Freezes when the monster goes down (quest end if
                  nothing did), matching the in-game meter.</span>
                </button>
              </div>
            </section>

            <section aria-label="Hunt exports folders">
              <h3>Hunt exports folders</h3>
              {exportDirs.length > 0 && (
                <ul className="settings-dirs">
                  {exportDirs.map((dir) => (
                    <li key={dir}>
                      <span title={dir}>{dir}</span>
                      <button type="button" aria-label={`Remove ${dir}`}
                        disabled={saving}
                        onClick={() => saveDirs(exportDirs.filter((d) => d !== dir))}>
                        ✕
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="settings-add">
                <input type="text" value={newDir} aria-label="Hunt exports folder"
                  placeholder="C:\...\reframework\data\HuntExports"
                  disabled={saving}
                  onChange={(e) => setNewDir(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") addDir(); }} />
                <button type="button" onClick={addDir}
                  disabled={saving || !newDir.trim()}>Add</button>
              </div>
              <p className="settings-hint">
                Extra folders to scan, e.g. a Mod Organizer 2 instance:
                {" "}<code>&lt;instance&gt;\overwrite\reframework\data\HuntExports</code>.
                {envOverride && <> <b>$HUNT_EXPORTS</b> is set and overrides this list.</>}
              </p>
              {missing.length > 0 && (
                <p className="settings-hint warn">
                  Not found yet: {missing.join(", ")}
                </p>
              )}
              {detected.length > 0 && (
                <p className="settings-hint" title={detected.map((s) => s.path).join("\n")}>
                  Active sources: {detected.map((s) => s.kind).join(" + ")}.
                </p>
              )}
            </section>

            <section aria-label="Data">
              <h3>Data</h3>
              <label className="settings-row settings-check">
                <input type="checkbox" checked={includeFailed}
                  onChange={(e) => onIncludeFailed(e.target.checked)} />
                <span>Include failed hunts</span>
              </label>
              <p className="settings-hint">
                Counts carted-out quests in performance stats. Clear rates always
                count failures, and hunts that never engaged a target aren&apos;t
                recorded at all.
              </p>
              <label className="settings-row settings-check">
                <input type="checkbox" checked={checkUpdates}
                  onChange={(e) => onCheckUpdates(e.target.checked)} />
                <span>Check for updates</span>
              </label>
              <p className="settings-hint">
                Asks GitHub for the latest release so the app can update itself in
                place. Off = no network requests at all.
                {appVersion ? <> · you have <b>v{appVersion}</b></> : null}
              </p>
            </section>
          </div>
        </Modal>
      )}
    </>
  );
}
