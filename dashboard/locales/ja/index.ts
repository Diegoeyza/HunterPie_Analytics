/** Composed Japanese dictionary.
 *
 *  Two guards: `Messages` (below) makes tsc reject a missing key, and the
 *  parity script (`scripts/check-i18n.mjs`, run in CI) reports per-area key
 *  gaps and placeholder drift in readable form.
 */
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
import type { Messages } from "../en";

export const ja: Messages = {
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
