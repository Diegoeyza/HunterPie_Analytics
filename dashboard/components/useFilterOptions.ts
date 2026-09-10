"use client";

import { useEffect, useState } from "react";
import { apiGetCached, type FilterOptions } from "../lib/api";

/** Fetch /filter-options once; shared by all filter bars (60s cache). */
export function useFilterOptions(): FilterOptions | null {
  const [opts, setOpts] = useState<FilterOptions | null>(null);
  useEffect(() => {
    apiGetCached<FilterOptions>("/filter-options").then(setOpts).catch(() => {});
  }, []);
  return opts;
}
