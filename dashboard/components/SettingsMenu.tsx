"use client";

import { useEffect, useState } from "react";
import { apiGet, apiInvalidate, apiPut, apiSend, type AppSettings, type ImportJobStatus } from "../lib/api";
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
  checkUpdates, onCheckUpdates, appVersion, onWhatsNew }: {
  includeFailed: boolean;
  onIncludeFailed: (value: boolean) => void;
  checkUpdates: boolean;
  onCheckUpdates: (value: boolean) => void;
  appVersion?: string;
  onWhatsNew?: () => void;
}) {
  const [theme, setTheme] = useState<Theme>("dark");
  const [open, setOpen] = useState(false);
  const [exportDirs, setExportDirs] = useState<string[]>([]);
  const [missing, setMissing] = useState<string[]>([]);
  const [detected, setDetected] = useState<AppSettings["detected"]>([]);
  const [envOverride, setEnvOverride] = useState(false);
  const [newDir, setNewDir] = useState("");
  const [dpsWindow, setDpsWindow] = useState("quest");
  const [questTargetsOnly, setQuestTargetsOnly] = useState(false);
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
        setQuestTargetsOnly(s.quest_targets_only === true);
      })
      .catch(() => { /* settings are optional; imports still auto-detect */ });
  }, []);

  const saveSettings = async (dirs: string[], window: string, targetsOnly: boolean) => {
    setSaving(true);
    try {
      const s = await apiPut<AppSettings>("/settings", {
        export_dirs: dirs, dps_window: window, quest_targets_only: targetsOnly,
      });
      setExportDirs(s.export_dirs);
      setMissing(s.missing);
      setDetected(s.detected);
      setEnvOverride(s.env_override);
      setDpsWindow(s.dps_window === "quest" ? "quest" : "engagement");
      setQuestTargetsOnly(s.quest_targets_only === true);
      setNewDir("");
      apiInvalidate();
      return s;
    } catch (e) {
      toast.push(e instanceof Error ? e.message : "Could not save settings", true);
      return null;
    } finally {
      setSaving(false);
    }
  };

  const saveDirs = async (dirs: string[]) => {
    const saved = await saveSettings(dirs, dpsWindow, questTargetsOnly);
    if (saved) toast.push(missing.length > 0
      ? "Saved. That folder doesn't exist yet — it will be scanned once it does."
      : "Hunt exports folder saved");
    return saved !== null;
  };

  const saveDpsWindow = async (window: string) => {
    setDpsWindow(window);
    const saved = await saveSettings(exportDirs, window, questTargetsOnly);
    if (saved) toast.push(window === "quest"
      ? "DPS now divides by own first hit → quest end"
      : "DPS now divides by first → last hit");
    return saved !== null;
  };

  // Hide/restore non-objective hunts. The backend applies it to every hunt
  // whose quest-target identity is already stored; when older companion hunts
  // have none, recheck the exports in the background to backfill them.
  const saveQuestTargetsOnly = async (next: boolean) => {
    setQuestTargetsOnly(next);
    const saved = await saveSettings(exportDirs, dpsWindow, next);
    if (!saved) return;
    if (!next) {
      toast.push("Quest-objective filter off — auto-hidden hunts restored");
      return;
    }
    const hidden = saved.filter_applied ?? 0;
    const unknown = saved.unknown_targets ?? 0;
    if (unknown === 0) {
      toast.push(hidden > 0
        ? `Filter on — ${hidden} hunt${hidden === 1 ? "" : "s"} hidden`
        : "Quest-objective filter on");
      return;
    }
    try {
      const job = await apiSend<{ job_id: string }>("POST", "/import?force=1");
      toast.push(`Filter on — rechecking exports to cover ${unknown} older hunt(s)…`);
      for (;;) {
        await new Promise((r) => setTimeout(r, 1000));
        try {
          const st = await apiGet<ImportJobStatus>("/import/status", { job_id: job.job_id });
          if (st.state === "running") continue;
          apiInvalidate();
          if (st.state === "done") {
            toast.push(`Quest-objective filter applied — ${st.scanned} export(s) rechecked`);
          }
          break;
        } catch {
          break; // job gone (app restarted): nothing more to report
        }
      }
    } catch {
      toast.push("Filter applied to known hunts; older hunts need Full recheck "
        + "(another import may be running)", true);
    }
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
                <input type="checkbox" checked={questTargetsOnly} disabled={saving}
                  onChange={(e) => saveQuestTargetsOnly(e.target.checked)} />
                <span>Only quest objectives</span>
              </label>
              <p className="settings-hint">
                Hides hunts whose monster was not the quest objective — an
                invading Guardian Rathalos, for example — exactly like pressing
                Ignore. Applies to older hunts too when the companion recorded
                which monsters were targets; turning it off restores them. Your
                own ignores are always kept.
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
                {onWhatsNew ? (
                  <> · <button type="button" className="link-button"
                    onClick={() => { setOpen(false); onWhatsNew(); }}>
                    What&apos;s new
                  </button></>
                ) : null}
              </p>
            </section>
          </div>
        </Modal>
      )}
    </>
  );
}
