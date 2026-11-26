import type { ReactNode } from "react";
import type { MessageKey } from "../locales/en";
import ProgressView from "../components/views/ProgressView";
import GrowthView from "../components/views/GrowthView";
import WeaponsView from "../components/views/WeaponsView";
import HighlightsView from "../components/views/HighlightsView";
import CurveView from "../components/views/CurveView";
import HuntsView from "../components/views/HuntsView";
import SurvivalView from "../components/views/SurvivalView";
import LeaderboardView from "../components/views/LeaderboardView";
import CompareView from "../components/views/CompareView";
import ActivityView from "../components/views/ActivityView";
import SynergyView from "../components/views/SynergyView";
import BuffsView from "../components/views/BuffsView";
import HighScoreView from "../components/views/HighScoreView";

export interface ViewCtx {
  /** Hunter scope: player ids to focus on. Empty = all hunters. */
  scope: number[];
  /** Weapon-variant scope (WeaponIdentity id, 0 = unknown-gear hunts).
   *  Only set with exactly one scoped hunter. Null = all variants. */
  variantId: number | string | null;
  /** Weapon-name scope (local player, from the REFramework mod; e.g.
   *  "Onyx Choros"). Only set with exactly one scoped hunter. */
  weaponName: string | null;
  /** Reset the hunter scope (passed to views for scope-aware empty states). */
  clearScope: () => void;
  /** Set the hunter scope to the given player ids. */
  setScope: (ids: number[]) => void;
  /** Global party-size filter: exact hunters per hunt. Null = all sizes. */
  partySize: number | null;
  /** Count failed (carted-out) hunts in performance stats (settings menu). */
  includeFailed: boolean;
}

export interface TabDef {
  id: string;
  /** Translation key for the tab label (`tab.<id>`). */
  title: MessageKey;
  /** Translation key for the one-line description under the tab bar. */
  blurb: MessageKey;
  render: (ctx: ViewCtx) => ReactNode;
}

/** ADDING A TAB = new file in components/views/ + one entry here. */
export const TABS: TabDef[] = [
  {
    id: "progress",
    title: "tab.progress",
    blurb: "tab.progress.blurb",
    render: (ctx) => <ProgressView scope={ctx.scope} variantId={ctx.variantId} weaponName={ctx.weaponName} clearScope={ctx.clearScope} partySize={ctx.partySize} includeFailed={ctx.includeFailed} />,
  },
  {
    id: "growth",
    title: "tab.growth",
    blurb: "tab.growth.blurb",
    render: (ctx) => <GrowthView scope={ctx.scope} variantId={ctx.variantId} weaponName={ctx.weaponName} clearScope={ctx.clearScope} partySize={ctx.partySize} setScope={ctx.setScope} includeFailed={ctx.includeFailed} />,
  },
  {
    id: "weapons",
    title: "tab.weapons",
    blurb: "tab.weapons.blurb",
    render: (ctx) => <WeaponsView scope={ctx.scope} variantId={ctx.variantId} weaponName={ctx.weaponName} clearScope={ctx.clearScope} partySize={ctx.partySize} includeFailed={ctx.includeFailed} />,
  },
  {
    id: "highlights",
    title: "tab.highlights",
    blurb: "tab.highlights.blurb",
    render: (ctx) => <HighlightsView scope={ctx.scope} weaponName={ctx.weaponName} partySize={ctx.partySize} includeFailed={ctx.includeFailed} />,
  },
  {
    id: "curves",
    title: "tab.curves",
    blurb: "tab.curves.blurb",
    render: (ctx) => <CurveView scope={ctx.scope} partySize={ctx.partySize} />,
  },
  {
    id: "hunts",
    title: "tab.hunts",
    blurb: "tab.hunts.blurb",
    render: (ctx) => <HuntsView scope={ctx.scope} weaponName={ctx.weaponName} partySize={ctx.partySize} includeFailed={ctx.includeFailed} />,
  },
  {
    id: "survival",
    title: "tab.survival",
    blurb: "tab.survival.blurb",
    render: (ctx) => <SurvivalView scope={ctx.scope} partySize={ctx.partySize} />,
  },
  {
    id: "leaderboard",
    title: "tab.leaderboard",
    blurb: "tab.leaderboard.blurb",
    render: (ctx) => <LeaderboardView scope={ctx.scope} variantId={ctx.variantId} weaponName={ctx.weaponName} clearScope={ctx.clearScope} partySize={ctx.partySize} includeFailed={ctx.includeFailed} />,
  },
  {
    id: "high-scores",
    title: "tab.highscores",
    blurb: "tab.highscores.blurb",
    render: (ctx) => <HighScoreView scope={ctx.scope} variantId={ctx.variantId} weaponName={ctx.weaponName} clearScope={ctx.clearScope} partySize={ctx.partySize} includeFailed={ctx.includeFailed} />,
  },
  {
    id: "compare",
    title: "tab.compare",
    blurb: "tab.compare.blurb",
    render: (ctx) => <CompareView scope={ctx.scope} variantId={ctx.variantId} clearScope={ctx.clearScope} partySize={ctx.partySize} includeFailed={ctx.includeFailed} />,
  },
  {
    id: "activity",
    title: "tab.activity",
    blurb: "tab.activity.blurb",
    render: (ctx) => <ActivityView partySize={ctx.partySize} />,
  },
  {
    id: "synergy",
    title: "tab.synergy",
    blurb: "tab.synergy.blurb",
    render: (ctx) => <SynergyView scope={ctx.scope} variantId={ctx.variantId} clearScope={ctx.clearScope} partySize={ctx.partySize} includeFailed={ctx.includeFailed} />,
  },
  {
    id: "buffs",
    title: "tab.buffs",
    blurb: "tab.buffs.blurb",
    render: (ctx) => <BuffsView scope={ctx.scope} partySize={ctx.partySize} />,
  },
];
