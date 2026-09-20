/** Shared number/time formatting. Use these instead of per-view copies. */

export const fmtTime = (s: number | null | undefined): string => {
  if (s === null || s === undefined) return "—";
  return `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
};

export const fmtDps = (d: number | null | undefined, digits = 1): string =>
  d === null || d === undefined ? "—" : d.toFixed(digits);

export const fmtPct = (f: number | null | undefined, digits = 0): string =>
  f === null || f === undefined ? "—" : `${(f * 100).toFixed(digits)}%`;

export const fmtInt = (n: number | null | undefined): string =>
  n === null || n === undefined ? "—" : Math.round(n).toLocaleString();

export const fmtDate = (iso: string | null | undefined): string =>
  !iso ? "—" : iso.slice(0, 10);

/** Round DPS for chart points (one decimal keeps tooltips readable). */
export const roundDps = (d: number): number => Math.round(d * 10) / 10;
