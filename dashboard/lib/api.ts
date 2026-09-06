/** Typed fetch helpers for the FastAPI backend.
 *  Override with NEXT_PUBLIC_API_URL (default http://localhost:8000).
 */
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiGet<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(`/api${path}`, BASE);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== "" && v !== undefined) url.searchParams.set(k, String(v));
    }
  }
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return (await res.json()) as T;
}

export interface Health { status: string; hunts: number; }
export interface Option { id: number; name: string; }
export interface FilterOptions { monsters: Option[]; weapons: Option[]; players: Option[]; }
export interface HuntSummary {
  id: number; monster: string; started_at: string;
  clear_s: number | null; cleared: boolean; carts: number; players: number;
}

export const PALETTE = [
  "#e8b64c", "#5aa9e6", "#58b368", "#e05c5c",
  "#9d7bff", "#4dd0c4", "#ef8354", "#7fb069",
];
export const seriesColor = (i: number) => PALETTE[i % PALETTE.length];
