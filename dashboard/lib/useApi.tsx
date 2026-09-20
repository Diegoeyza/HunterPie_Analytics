"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGetCached, apiInvalidate } from "./api";

export type ApiParams = Record<string, string | number | null | undefined>;

/** Stable effect key: sorted params so {a:1,b:2} === {b:2,a:1}. */
export function apiKey(path: string, params?: ApiParams): string {
  const parts: string[] = [path];
  if (params) {
    for (const k of Object.keys(params).sort()) {
      const v = params[k];
      if (v !== "" && v !== undefined && v !== null) parts.push(`${k}=${v}`);
    }
  }
  return parts.join("?");
}

export interface UseApiResult<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  refetch: () => void;
}

/** SWR-lite: cached GET with loading/error states + manual refetch.
 *
 *  Replaces the per-view useState+useEffect+apiGet boilerplate (and the
 *  `scope.join(",")` exhaustive-deps anti-pattern — the effect keys on a
 *  stable string). Pass `null` params to skip the request (two-stage
 *  views: list first, detail when selected).
 */
export function useApi<T>(path: string, params?: ApiParams | null): UseApiResult<T> {
  const key = params === null ? null : apiKey(path, params);
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (key === null) {
      setData(null);
      setError(null);
      return;
    }
    // Per-request liveness flag (no shared ref: StrictMode double-effects
    // and Fast Refresh must never permanently block later resolutions).
    let live = true;
    setError(null);
    apiGetCached<T>(path, params ?? undefined)
      .then((d) => { if (live) setData(d); })
      .catch((e: Error) => { if (live) setError(e.message); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, nonce]);

  const refetch = useCallback(() => {
    apiInvalidate(path);
    setNonce((n) => n + 1);
  }, [path]);

  return { data, error, loading: key !== null && data === null && error === null, refetch };
}

/** Shared view states: error / loading / empty, one consistent look. */
export function ApiState({ error, loading, empty }: { error: string | null; loading: boolean; empty?: React.ReactNode }) {
  if (error) return <p className="error">{error} — is the API running on :8000?</p>;
  if (loading) return <p>Loading…</p>;
  if (empty) return <>{empty}</>;
  return null;
}
