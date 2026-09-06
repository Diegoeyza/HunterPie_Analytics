import type { ReactNode } from "react";
import ProgressView from "../components/views/ProgressView";
import WeaponsView from "../components/views/WeaponsView";
import CurveView from "../components/views/CurveView";
import SynergyView from "../components/views/SynergyView";

export interface TabDef {
  id: string;
  title: string;
  blurb: string;
  render: () => ReactNode;
}

/** ADDING A TAB = new file in components/views/ + one entry here. */
export const TABS: TabDef[] = [
  {
    id: "progress",
    title: "Progress",
    blurb: "FR-3.1 — rolling DPS and clear time per hunt, filterable by monster, weapon, hunter.",
    render: () => <ProgressView />,
  },
  {
    id: "weapons",
    title: "Weapons",
    blurb: "FR-3.2 — avg/peak DPS, hunt count and clear rate by weapon type.",
    render: () => <WeaponsView />,
  },
  {
    id: "curves",
    title: "Damage curves",
    blurb: "FR-3.3 — per-hunt cumulative damage overlay for all party members, with enrage markers.",
    render: () => <CurveView />,
  },
  {
    id: "synergy",
    title: "Synergy",
    blurb: "FR-3.4 — clear time and damage share by teammate pairing (supporters excluded).",
    render: () => <SynergyView />,
  },
];
