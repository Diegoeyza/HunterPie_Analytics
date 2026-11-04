"use client";

import type { FilterOptions } from "../lib/api";
import { useApi } from "../lib/useApi";

/** Fetch /filter-options and keep it in sync with imports/pins.
 *
 *  The shared API cache has a 60 s TTL, but a mounted page can outlive it.
 *  useApi subscribes to apiInvalidate(), so an import refreshes the hunter
 *  list immediately instead of leaving the search bar on stale options. */
export function useFilterOptions(): FilterOptions | null {
  return useApi<FilterOptions>("/filter-options").data;
}
