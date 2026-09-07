/** Shared number/time formatting. Use these instead of per-view copies. */

export const fmtTime = (s: number | null | undefined): string => {
  if (s === null || s === undefined) return "—";
  return `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
};

export const fmtDps = (d: number | null | undefined, digits = 1): string =>
  d === null || d === undefined ? "—" : d.toFixed(digits);

export const fmtPct = (f: number | null | undefined, digits = 0): string =>
  f === null || f === undefined ? "—" : `${(f * 100).toFixed(digits)}%`;
