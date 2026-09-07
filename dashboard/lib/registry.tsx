import type { ReactNode } from "react";
import ProgressView from "../components/views/ProgressView";
import WeaponsView from "../components/views/WeaponsView";
import CurveView from "../components/views/CurveView";
import QuestsView from "../components/views/QuestsView";
import RecordsView from "../components/views/RecordsView";
import CompareView from "../components/views/CompareView";
import ActivityView from "../components/views/ActivityView";
import SynergyView from "../components/views/SynergyView";
import BuffsView from "../components/views/BuffsView";
import HighScoreView from "../components/views/HighScoreView";

export interface ViewCtx {
  /** Hunter scope: player ids to focus on. Empty = all hunters. */
  scope: number[];
}

export interface TabDef {
  id: string;
  title: string;
  blurb: string;
  render: (ctx: ViewCtx) => ReactNode;
}

/** ADDING A TAB = new file in components/views/ + one entry here. */
export const TABS: TabDef[] = [
  {
    id: "progress",
    title: "Progress",
    blurb: "FR-3.1 — rolling DPS and clear time per hunt, filterable by monster, quest, stars, weapon, hunter.",
    render: (ctx) => <ProgressView scope={ctx.scope} />,
  },
  {
    id: "weapons",
    title: "Weapons",
    blurb: "FR-3.2 — avg/peak DPS, hunt count and clear rate by weapon type.",
    render: (ctx) => <WeaponsView scope={ctx.scope} />,
  },
  {
    id: "curves",
    title: "Damage curves",
    blurb: "FR-3.3 — per-hunt cumulative damage overlay for all party members, monster HP curve, enrage markers.",
    render: (ctx) => <CurveView scope={ctx.scope} />,
  },
  {
    id: "quests",
    title: "Quests",
    blurb: "Same monster, different HP per quest — per-quest clear stats, best DPS and enrage uptime.",
    render: () => <QuestsView />,
  },
  {
    id: "records",
    title: "Records",
    blurb: "Personal bests per monster: fastest clear and highest single-hunt DPS.",
    render: () => <RecordsView />,
  },
  {
    id: "high-scores",
    title: "High Scores",
    blurb: "Leaderboard filtering per player, monster, weapon, and stars, sorted by fastest clear time or highest DPS with full party breakdown.",
    render: (ctx) => <HighScoreView scope={ctx.scope} />,
  },
  {
    id: "compare",
    title: "Compare",
    blurb: "Your scoped hunters vs the whole party, hunt by hunt. Star yourself in the hunters bar above.",
    render: (ctx) => <CompareView scope={ctx.scope} />,
  },
  {
    id: "activity",
    title: "Activity",
    blurb: "Hunt volume, clear rate and damage output day by day.",
    render: () => <ActivityView />,
  },
  {
    id: "synergy",
    title: "Synergy",
    blurb: "FR-3.4 — clear time and damage share by teammate pairing (supporters excluded).",
    render: (ctx) => <SynergyView scope={ctx.scope} />,
  },
  {
    id: "buffs",
    title: "Buffs",
    blurb: "Consumable, skill, song and debuff uptime per player per hunt. HunterPie user only.",
    render: (ctx) => <BuffsView scope={ctx.scope} />,
  },
];
