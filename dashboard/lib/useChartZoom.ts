"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { MouseHandlerDataParam } from "recharts";

export type TimeRange = [number, number];
type Domain = [number | string, number | string];

function timeOf(label: MouseHandlerDataParam["activeLabel"]): number | null {
  const value = typeof label === "number" ? label : Number(label);
  return Number.isFinite(value) ? value : null;
}

/** Drag-to-zoom for a numeric time axis.
 *
 *  Click-drag across the plot to select a time window; double-click (or the
 *  caller's reset control) restores the full domain. The hook only changes
 *  the X domain — Y axes stay untouched, so magnitude remains comparable.
 */
export function useChartZoom(resetKey: unknown) {
  const [range, setRange] = useState<TimeRange | null>(null);
  const [drag, setDrag] = useState<TimeRange | null>(null);
  const dragRef = useRef<TimeRange | null>(null);

  const updateDrag = useCallback((next: TimeRange | null) => {
    dragRef.current = next;
    setDrag(next);
  }, []);

  const reset = useCallback(() => {
    dragRef.current = null;
    setDrag(null);
    setRange(null);
  }, []);

  // A different hunt should always start at the full timeline.
  useEffect(() => {
    reset();
  }, [resetKey, reset]);

  const onMouseDown = useCallback((state: MouseHandlerDataParam) => {
    const t = timeOf(state.activeLabel);
    if (t !== null) updateDrag([t, t]);
  }, [updateDrag]);

  const onMouseMove = useCallback((state: MouseHandlerDataParam) => {
    const current = dragRef.current;
    if (!current) return;
    const t = timeOf(state.activeLabel);
    if (t !== null) updateDrag([current[0], t]);
  }, [updateDrag]);

  const onMouseUp = useCallback(() => {
    const current = dragRef.current;
    if (!current) return;
    const lo = Math.min(current[0], current[1]);
    const hi = Math.max(current[0], current[1]);
    if (hi - lo >= 2) setRange([lo, hi]);
    updateDrag(null);
  }, [updateDrag]);

  const selection = useMemo<TimeRange | null>(() => {
    if (!drag) return null;
    return [Math.min(drag[0], drag[1]), Math.max(drag[0], drag[1])];
  }, [drag]);

  const domain = useMemo<Domain>(
    () => (range ? [range[0], range[1]] : ["dataMin", "dataMax"]),
    [range]
  );

  return {
    domain,
    range,
    selection,
    zoomed: range !== null,
    reset,
    handlers: {
      onMouseDown,
      onMouseMove,
      onMouseUp,
      onMouseLeave: onMouseUp,
      onDoubleClick: reset,
    },
  };
}
