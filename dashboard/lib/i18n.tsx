"use client";

/** Tiny client-side i18n. No routing: the dashboard is a static export with
 *  tab state, so the locale is a UI preference (localStorage + `?lang=`), not
 *  a URL segment.
 *
 *  Two ways to translate:
 *   - components: `const { t, locale, setLocale } = useT();`
 *   - non-component helpers (format.ts, metric labels): plain `t(key, vars)`,
 *     which reads the locale the provider last applied. Every component
 *     re-renders when the locale changes, so the mirror is always current by
 *     the time those helpers run.
 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from "react";
import { en, type MessageKey, type Messages } from "../locales/en";
import { ja } from "../locales/ja";
import { writeParams } from "./url";

export type Locale = "en" | "ja";

/** Locale preference key (localStorage) and the `?lang=` URL override. */
export const LOCALE_KEY = "hp.locale";
export const LANG_PARAM = "lang";

export const LOCALES: { id: Locale; label: string }[] = [
  { id: "en", label: "English" },
  { id: "ja", label: "日本語" },
];

const DICTS: Record<Locale, Messages> = { en, ja };

/** The active locale, mirrored for non-hook call sites. */
let active: Locale = "en";
export function currentLocale(): Locale {
  return active;
}
/** BCP-47 tag for `Intl` formatting. */
export function localeTag(): string {
  return active === "ja" ? "ja-JP" : "en-US";
}

const warned = new Set<string>();
export type Vars = Record<string, string | number>;

/** Translate a key known at compile time, interpolating `{name}`
 *  placeholders. Missing keys fall back to English, then to the key itself
 *  (never blank) — the literal-key scan in `scripts/check-i18n.mjs` keeps
 *  those fallbacks from ever shipping. */
export function t(key: MessageKey, vars?: Vars): string {
  return translate(key, vars);
}

/** Same lookup for runtime-built keys (`settings.source.${kind}`,
 *  `weapon.${type}`). Callers keep a `label === key` fallback for values the
 *  dictionary does not know. */
export function tDynamic(key: string, vars?: Vars): string {
  return translate(key, vars);
}

function translate(key: string, vars?: Vars): string {
  const dict = DICTS[active] ?? en;
  const raw = (dict as Record<string, string | undefined>)[key]
    ?? (en as Record<string, string | undefined>)[key];
  if (raw === undefined) {
    if (process.env.NODE_ENV !== "production" && !warned.has(key)) {
      warned.add(key);
      console.warn(`[i18n] missing key: ${key}`);
    }
    return key;
  }
  if (!vars) return raw;
  return raw.replace(/\{(\w+)\}/g, (m, name: string) =>
    name in vars ? String(vars[name]) : m);
}

export function loadLocale(): Locale {
  if (typeof window === "undefined") return "en";
  try {
    const fromUrl = new URLSearchParams(window.location.search).get(LANG_PARAM);
    if (fromUrl === "ja" || fromUrl === "en") return fromUrl;
  } catch { /* no window.location */ }
  try {
    const stored = localStorage.getItem(LOCALE_KEY);
    if (stored === "ja" || stored === "en") return stored;
  } catch { /* private mode */ }
  const nav = (navigator.language || "").toLowerCase();
  return nav.startsWith("ja") ? "ja" : "en";
}

export function storeLocale(locale: Locale): void {
  try {
    localStorage.setItem(LOCALE_KEY, locale);
  } catch { /* private mode: preference just won't persist */ }
}

interface Ctx {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: typeof t;
}

const I18nCtx = createContext<Ctx>({ locale: "en", setLocale: () => {}, t });

export function I18nProvider({ children }: { children: ReactNode }) {
  // Server/prerender paints English; the mount effect switches to the stored
  // or navigator locale. That keeps the static export hydration-stable.
  const [locale, setLocaleState] = useState<Locale>("en");
  active = locale;

  useEffect(() => {
    setLocaleState(loadLocale());
  }, []);

  useEffect(() => {
    active = locale;
    document.documentElement.lang = locale === "ja" ? "ja" : "en";
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    active = next;
    setLocaleState(next);
    storeLocale(next);
    document.documentElement.lang = next === "ja" ? "ja" : "en";
    // An explicit choice wins over a stale `?lang=` from a shared link,
    // otherwise a reload would silently undo it.
    writeParams({ [LANG_PARAM]: null });
  }, []);

  const value = useMemo<Ctx>(() => ({ locale, setLocale, t }), [locale, setLocale]);
  return <I18nCtx.Provider value={value}>{children}</I18nCtx.Provider>;
}

/** Signature shared by components that receive `t` from `useT()`. */
export type TFn = typeof t;

export function useT(): Ctx {
  return useContext(I18nCtx);
}
