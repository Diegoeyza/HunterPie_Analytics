"use client";

import { useEffect, useState } from "react";
import { apiGet, apiInvalidate, apiPut, apiSend, type AppSettings, type ImportJobStatus } from "../lib/api";
import Modal from "./Modal";
import { useToast } from "./Toast";
import { LOCALES, tDynamic, useT } from "../lib/i18n";

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
  const { locale, setLocale, t } = useT();

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
      toast.push(e instanceof Error ? e.message : t("settings.toast.saveFailed"), true);
      return null;
    } finally {
      setSaving(false);
    }
  };

  const saveDirs = async (dirs: string[]) => {
    const saved = await saveSettings(dirs, dpsWindow, questTargetsOnly);
    if (saved) toast.push(missing.length > 0
      ? t("settings.toast.savedMissing")
      : t("settings.toast.saved"));
    return saved !== null;
  };

  const saveDpsWindow = async (window: string) => {
    setDpsWindow(window);
    const saved = await saveSettings(exportDirs, window, questTargetsOnly);
    if (saved) toast.push(window === "quest"
      ? t("settings.toast.dpsQuest")
      : t("settings.toast.dpsEngagement"));
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
      toast.push(t("settings.toast.filterOff"));
      return;
    }
    const hidden = saved.filter_applied ?? 0;
    const unknown = saved.unknown_targets ?? 0;
    if (unknown === 0) {
      toast.push(hidden > 0
        ? t(hidden === 1
          ? "settings.toast.huntsHidden.one"
          : "settings.toast.huntsHidden.other", { n: hidden })
        : t("settings.toast.filterOn"));
      return;
    }
    try {
      const job = await apiSend<{ job_id: string }>("POST", "/import?force=1");
      toast.push(t("settings.toast.rechecking", { n: unknown }));
      for (;;) {
        await new Promise((r) => setTimeout(r, 1000));
        try {
          const st = await apiGet<ImportJobStatus>("/import/status", { job_id: job.job_id });
          if (st.state === "running") continue;
          apiInvalidate();
          if (st.state === "done") {
            toast.push(t("settings.toast.rechecked", { n: st.scanned }));
          }
          break;
        } catch {
          break; // job gone (app restarted): nothing more to report
        }
      }
    } catch {
      toast.push(t("settings.toast.filterPartial"), true);
    }
  };

  const addDir = async () => {
    const value = newDir.trim();
    if (!value || saving) return;
    await saveDirs([...exportDirs, value]);
  };

  return (
    <>
      <button type="button" className="settings-open" title={t("settings.title")}
        aria-label={t("settings.title")} aria-haspopup="dialog"
        onClick={() => setOpen(true)}>⚙</button>
      {open && (
        <Modal label={t("settings.title")} onClose={() => setOpen(false)}>
          <div className="modal-head">
            <h2>{t("settings.title")}</h2>
            <button type="button" className="row-action"
              onClick={() => setOpen(false)}>{t("common.close")}</button>
          </div>
          <div className="settings-page">
            <section aria-label={t("settings.display")}>
              <h3>{t("settings.display")}</h3>
              <div className="settings-row">
                <span>{t("settings.theme")}</span>
                <div className="seg" role="group" aria-label={t("settings.theme")}>
                  <button type="button" className={theme === "dark" ? "on" : ""}
                    aria-pressed={theme === "dark"}
                    onClick={() => setTheme("dark")}>{t("settings.themeDark")}</button>
                  <button type="button" className={theme === "light" ? "on" : ""}
                    aria-pressed={theme === "light"}
                    onClick={() => setTheme("light")}>{t("settings.themeLight")}</button>
                </div>
              </div>
              <div className="settings-row">
                <span>{t("settings.language")}</span>
                <div className="seg" role="group" aria-label={t("settings.language")}>
                  {LOCALES.map((l) => (
                    <button key={l.id} type="button" className={locale === l.id ? "on" : ""}
                      aria-pressed={locale === l.id}
                      onClick={() => setLocale(l.id)}>{l.label}</button>
                  ))}
                </div>
              </div>
            </section>

            <section aria-label={t("settings.dpsWindow")}>
              <h3>{t("settings.dpsWindow")}</h3>
              <div className="settings-choices" role="radiogroup" aria-label={t("settings.dpsWindow")}>
                <button type="button" role="radio"
                  aria-checked={dpsWindow === "engagement"}
                  className={dpsWindow === "engagement" ? "on" : ""}
                  disabled={saving}
                  onClick={() => saveDpsWindow("engagement")}>
                  <b>{t("settings.dpsEngagementTitle")}</b>
                  <span>{t("settings.dpsEngagementBody")}</span>
                </button>
                <button type="button" role="radio"
                  aria-checked={dpsWindow === "quest"}
                  className={dpsWindow === "quest" ? "on" : ""}
                  disabled={saving}
                  onClick={() => saveDpsWindow("quest")}>
                  <b>{t("settings.dpsQuestTitle")}</b>
                  <span>{t("settings.dpsQuestBody")}</span>
                </button>
              </div>
            </section>

            <section aria-label={t("settings.exports")}>
              <h3>{t("settings.exports")}</h3>
              {exportDirs.length > 0 && (
                <ul className="settings-dirs">
                  {exportDirs.map((dir) => (
                    <li key={dir}>
                      <span title={dir}>{dir}</span>
                      <button type="button" aria-label={t("settings.exportsRemove", { dir })}
                        disabled={saving}
                        onClick={() => saveDirs(exportDirs.filter((d) => d !== dir))}>
                        ✕
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="settings-add">
                <input type="text" value={newDir} aria-label={t("settings.exportsFolder")}
                  placeholder="C:\...\reframework\data\HuntExports"
                  disabled={saving}
                  onChange={(e) => setNewDir(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") addDir(); }} />
                <button type="button" onClick={addDir}
                  disabled={saving || !newDir.trim()}>{t("common.add")}</button>
              </div>
              <p className="settings-hint">
                {t("settings.exportsHintLead")}
                {" "}<code>&lt;instance&gt;\overwrite\reframework\data\HuntExports</code>{t("settings.exportsHintTail")}
                {envOverride && <> <b>$HUNT_EXPORTS</b>{t("settings.exportsEnvSuffix")}</>}
              </p>
              {missing.length > 0 && (
                <p className="settings-hint warn">
                  {t("settings.exportsMissing", { dirs: missing.join(", ") })}
                </p>
              )}
              {detected.length > 0 && (
                <p className="settings-hint" title={detected.map((s) => s.path).join("\n")}>
                  {t("settings.exportsActive", {
                    kinds: detected
                      .map((s) => tDynamic(`settings.source.${s.kind}`))
                      .join(" + "),
                  })}
                </p>
              )}
            </section>

            <section aria-label={t("settings.data")}>
              <h3>{t("settings.data")}</h3>
              <label className="settings-row settings-check">
                <input type="checkbox" checked={includeFailed}
                  onChange={(e) => onIncludeFailed(e.target.checked)} />
                <span>{t("settings.includeFailed")}</span>
              </label>
              <p className="settings-hint">
                {t("settings.includeFailedHint")}
              </p>
              <label className="settings-row settings-check">
                <input type="checkbox" checked={questTargetsOnly} disabled={saving}
                  onChange={(e) => saveQuestTargetsOnly(e.target.checked)} />
                <span>{t("settings.questTargetsOnly")}</span>
              </label>
              <p className="settings-hint">
                {t("settings.questTargetsOnlyHint")}
              </p>
              <label className="settings-row settings-check">
                <input type="checkbox" checked={checkUpdates}
                  onChange={(e) => onCheckUpdates(e.target.checked)} />
                <span>{t("settings.checkUpdates")}</span>
              </label>
              <p className="settings-hint">
                {t("settings.checkUpdatesHint")}
                {appVersion ? <> · {t("settings.versionLabel")} <b>v{appVersion}</b></> : null}
                {onWhatsNew ? (
                  <> · <button type="button" className="link-button"
                    onClick={() => { setOpen(false); onWhatsNew(); }}>
                    {t("settings.whatsNew")}
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
