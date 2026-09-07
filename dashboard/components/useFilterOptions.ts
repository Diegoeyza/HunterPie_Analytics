"use client";

import { useEffect, useState } from "react";
import { apiGet, type FilterOptions } from "../lib/api";

/** Fetch /filter-options once; shared by all filter bars. */
export function useFilterOptions(): FilterOptions | null {
  const [opts, setOpts] = useState<FilterOptions | null>(null);
  useEffect(() => {
    apiGet<FilterOptions>("/filter-options").then(setOpts).catch(() => {});
  }, []);
  return opts;
}
