"use client";

import { useEffect, useState } from "react";

const THEME_KEY = "hp.theme";
type Theme = "dark" | "light";

export function loadTheme(): Theme {
  try {
    return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

/** Top-bar settings popover: theme + which hunts feed the stats.
 *  Persists theme to localStorage and applies it to <html data-theme>. */
export default function SettingsMenu({ includeFailed, onIncludeFailed }: {
  includeFailed: boolean;
  onIncludeFailed: (value: boolean) => void;
}) {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    setTheme(loadTheme());
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch { /* private mode: theme just won't persist */ }
  }, [theme]);

  return (
    <details className="settings">
      <summary title="Settings" aria-label="Settings">⚙</summary>
      <div className="settings-menu">
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
      </div>
    </details>
  );
}
