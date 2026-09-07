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

/** Dark/light toggle. Persists to localStorage, defaults to dark. */
export default function ThemeToggle() {
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
    <button
      type="button"
      className="theme-toggle"
      title={theme === "dark" ? "switch to light theme" : "switch to dark theme"}
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
    >
      {theme === "dark" ? "Light" : "Dark"}
    </button>
  );
}
