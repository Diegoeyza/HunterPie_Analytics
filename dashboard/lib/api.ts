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

export async function apiSend<T>(method: string, path: string): Promise<T> {
  const res = await fetch(new URL(`/api${path}`, BASE).toString(), { method });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return (await res.json()) as T;
}

/** Cached GET: 60s TTL + in-flight dedupe.
 *
 *  Every tab switch remounts its view and refires /filter-options; without
 *  caching that's a full round-trip per switch. Import/ignore actions
 *  hard-reload the page, and pin toggles call apiInvalidate(), so a short
 *  TTL is safe.
 */
const _cache = new Map<string, { at: number; data: unknown }>();
const _inflight = new Map<string, Promise<unknown>>();
const CACHE_TTL_MS = 60_000;

function cacheKey(path: string, params?: Record<string, string | number>): string {
  const url = new URL(`/api${path}`, BASE);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== "" && v !== undefined) url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

export async function apiGetCached<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const key = cacheKey(path, params);
  const hit = _cache.get(key);
  if (hit && Date.now() - hit.at < CACHE_TTL_MS) return hit.data as T;
  const ongoing = _inflight.get(key);
  if (ongoing) return ongoing as Promise<T>;
  const p = apiGet<T>(path, params).then((d) => {
    _cache.set(key, { at: Date.now(), data: d });
    _inflight.delete(key);
    return d;
  }).catch((e) => {
    _inflight.delete(key);
    throw e;
  });
  _inflight.set(key, p);
  return p;
}

/** Drop cached entries; call after mutations (pin/unpin). No arg = all. */
export function apiInvalidate(pathSubstring?: string): void {
  if (!pathSubstring) {
    _cache.clear();
    return;
  }
  for (const k of [..._cache.keys()]) {
    if (k.includes(pathSubstring)) _cache.delete(k);
  }
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(new URL(`/api${path}`, BASE).toString(), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return (await res.json()) as T;
}

export interface Health { status: string; hunts: number; }
export interface Option { id: number; name: string; }
export interface QuestOption { quest_id: number | null; monster: string; monster_id: number; stars: number | null; }
export interface FilterOptions {
  monsters: Option[]; weapons: Option[]; players: Option[];
  quests: QuestOption[]; stars: number[];
  monster_stars: Record<number, number[]>;
}
export interface Pin { player_id: number; name: string; pinned_at: string; }
export interface VariantOption {
  id: number | null; weapon_type: string;
  raw: number; element: number; affinity: number;
  label: string | null; hunts: number;
  /** Similarity group key (`g:<type>:<n>`); same-stat builds share one. */
  group: string;
}
export interface PlayerVariants {
  player_id: number; variants: VariantOption[]; unknown_hunts: number;
}
/** Pseudo id for hunts with no gear data (mirrors backend UNKNOWN_VARIANT_ID). */
export const UNKNOWN_VARIANT_ID = 0;

/** Display label: user name when labeled, else compact fingerprint. */
export const variantLabel = (v: VariantOption): string =>
  v.label ?? `${v.weapon_type} · ${Math.round(v.raw)} raw / ${Math.round(v.element)} el / ${Math.round(v.affinity)}%`;
export interface HuntSummary {
  id: number; monster: string; started_at: string;
  quest_id: number | null; quest_stars: number | null;
  clear_s: number | null; cleared: boolean; carts: number; players: number;
  ignored: boolean;
}

export const PALETTE = [
  "#e8b64c", "#5aa9e6", "#58b368", "#e05c5c",
  "#9d7bff", "#4dd0c4", "#ef8354", "#7fb069",
];
export const seriesColor = (i: number) => PALETTE[i % PALETTE.length];
