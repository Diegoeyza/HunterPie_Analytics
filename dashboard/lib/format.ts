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

/** Award value: unit 0 = count, 1 = time (mm'ss"cc), 2 = plain. */
export function fmtAward(value: number | null | undefined, unit: number): string {
  if (value === null || value === undefined) return "—";
  if (unit === 1) {
    const m = Math.floor(value / 60);
    const s = Math.floor(value % 60);
    const cs = Math.floor((value - Math.floor(value)) * 100);
    return `${String(m).padStart(2, "0")}'${String(s).padStart(2, "0")}"${String(cs).padStart(2, "0")}`;
  }
  if (unit === 0) return fmtInt(value);
  // unit 2 (none) and damage-like floats: show grouped, trimmed
  return Math.abs(value - Math.round(value)) < 1e-6
    ? fmtInt(value) : value.toFixed(1);
}

/** Award unit constants (mirror backend). */
export const AWARD_UNIT = { COUNT: 0, TIME: 1, NONE: 2 } as const;

/** Round DPS for chart points (one decimal keeps tooltips readable). */
export const roundDps = (d: number): number => Math.round(d * 10) / 10;
