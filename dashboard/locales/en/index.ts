/** Composed English dictionary. Adding a locale area = one import + one spread
 *  in BOTH index files; keys stay flat and prefixed per area. */
import common from "./common.json";
import names from "./names.json";
import scope from "./scope.json";
import settings from "./settings.json";
import table from "./table.json";
import tabs from "./tabs.json";
import activity from "./views.activity.json";
import buffs from "./views.buffs.json";
import compare from "./views.compare.json";
import curves from "./views.curves.json";
import growth from "./views.growth.json";
import highlights from "./views.highlights.json";
import highscores from "./views.highscores.json";
import hunts from "./views.hunts.json";
import leaderboard from "./views.leaderboard.json";
import progress from "./views.progress.json";
import survival from "./views.survival.json";
import synergy from "./views.synergy.json";
import weapons from "./views.weapons.json";

export const en = {
  ...common,
  ...names,
  ...scope,
  ...settings,
  ...table,
  ...tabs,
  ...activity,
  ...buffs,
  ...compare,
  ...curves,
  ...growth,
  ...highlights,
  ...highscores,
  ...hunts,
  ...leaderboard,
  ...progress,
  ...survival,
  ...synergy,
  ...weapons,
};

/** Every key the app may translate (drives autocomplete + the parity check). */
export type MessageKey = keyof typeof en;
export type Messages = Record<MessageKey, string>;
