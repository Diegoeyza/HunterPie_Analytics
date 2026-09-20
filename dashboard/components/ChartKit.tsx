"use client";

import { Tooltip } from "recharts";

/** Theme-aware chart constants. Colors resolve through CSS vars
 *  (--chart-grid/--chart-tick/--panel/--border) so charts stay readable
 *  in both dark and light mode (the old hardcoded dark values broke
 *  light mode). Add the vars to app/globals.css when theming.
 */
export const GRID_STROKE = "var(--chart-grid, #2c313e)";
export const TICK = { fill: "var(--chart-tick, #9aa1b2)", fontSize: 11 };
export const TIP_STYLE = {
  background: "var(--panel, #1d2029)",
  border: "1px solid var(--border, #2c313e)",
  color: "var(--text, #e6e9f0)",
};
export const AXIS_LABEL = { fill: "var(--chart-tick, #9aa1b2)", fontSize: 11 };

export function ChartTip() {
  return <Tooltip contentStyle={TIP_STYLE} />;
}
