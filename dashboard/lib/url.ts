"use client";

/** URL query-param state (shareable links, back-button support).
 *
 *  No router dependency: reads window.location on mount, writes via
 *  history.replaceState (no navigation, no Suspense boundary needed).
 *  localStorage remains the fallback default when the param is absent.
 */

export function readParam(key: string): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get(key);
}

export function writeParams(patch: Record<string, string | null>): void {
  if (typeof window === "undefined") return;
  const sp = new URLSearchParams(window.location.search);
  for (const [k, v] of Object.entries(patch)) {
    if (v === null || v === "") sp.delete(k);
    else sp.set(k, v);
  }
  const qs = sp.toString();
  window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
}

export function parseIds(raw: string | null): number[] {
  if (!raw) return [];
  return raw.split(",").map((s) => Number(s.trim())).filter((n) => Number.isInteger(n) && n > 0);
}
