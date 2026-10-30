/** Shared number/time formatting. Use these instead of per-view copies. */

/** Hunt durations as minutes:seconds ("9:07"). Rounding happens on the total
 *  so 539.7 s reads 9:00, never 8:60. */
export const fmtTime = (s: number | null | undefined): string => {
  if (s === null || s === undefined) return "—";
  const total = Math.max(0, Math.round(s));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
};

export const fmtDps = (d: number | null | undefined, digits = 1): string =>
  d === null || d === undefined ? "—" : d.toFixed(digits);

export const fmtPct = (f: number | null | undefined, digits = 0): string =>
  f === null || f === undefined ? "—" : `${(f * 100).toFixed(digits)}%`;

export const fmtInt = (n: number | null | undefined): string =>
  n === null || n === undefined ? "—" : Math.round(n).toLocaleString();

/** Backend timestamps are naive UTC (game dumps end in Z); a bare string
 *  would otherwise be parsed as local time and shift the date. */
const parseUtc = (iso: string): Date => {
  const zoned = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso);
  return new Date(zoned ? iso : `${iso}Z`);
};

const pad2 = (n: number): string => String(n).padStart(2, "0");

/** Local calendar date (YYYY-MM-DD). */
export const fmtDate = (iso: string | null | undefined): string => {
  if (!iso) return "—";
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
};

/** Local date + time (YYYY-MM-DD HH:mm). */
export const fmtDateTime = (iso: string | null | undefined): string => {
  if (!iso) return "—";
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 16).replace("T", " ");
  return `${fmtDate(iso)} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
};

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

/** Round DPS for chart points (one decimal keeps tooltips readable). */
export const roundDps = (d: number): number => Math.round(d * 10) / 10;
