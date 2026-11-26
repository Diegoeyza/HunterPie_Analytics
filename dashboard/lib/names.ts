/** Data-name translation (monsters, skills/abnormalities, awards, weapons).
 *
 *  Captured data keeps the names it had when the hunt was recorded, so a name
 *  is always resolved by ID and falls back to that stored English string —
 *  never blank, never a raw ID. `locales/ja/data.json` is generated from the
 *  game's own text (`scripts/gen_names_ja.py`); only the 30 quest awards and
 *  the 14 weapon classes are hand-maintained.
 */
import data from "../locales/ja/data.json";
import { currentLocale, t, tDynamic } from "./i18n";

type Table = Record<string, string>;

const MONSTERS = data.monsters as Table;
const ABNORMALITIES = data.abnormalities as Table;
const AWARDS = data.awards as Table;

const isJa = () => currentLocale() === "ja";

/** HunterPie emits ids as `{Group}_{Id}` where the `Id` already carries the
 *  group (`Skills_Skills.159-1`). The generated table is keyed by the inner
 *  form (`Skills.159-1`), so try the raw id and both de-duplicated spellings. */
function shortIdCandidates(id: string): string[] {
  const out = [id];
  const cut = id.indexOf("_");
  if (cut > 0) {
    const group = id.slice(0, cut);
    const rest = id.slice(cut + 1);
    out.push(rest);
    if (!rest.startsWith(`${group}.`)) out.push(`${group}.${rest}`);
  }
  return out;
}

/** Monster display name: Japanese game name when known, else as captured. */
export function monsterName(english: string | null | undefined, id?: number | null): string {
  if (isJa() && id !== null && id !== undefined) {
    const ja = MONSTERS[String(id)];
    if (ja) return ja;
  }
  return english || t("common.unknown");
}

/** Skill / consumable / debuff name by HunterPie id (`Skills_Skills.159-1`). */
export function abnormalityName(shortId: string | null | undefined,
                                 english: string | null | undefined): string {
  if (isJa() && shortId) {
    for (const candidate of shortIdCandidates(shortId)) {
      const ja = ABNORMALITIES[candidate];
      if (ja) return ja;
    }
  }
  return english || shortId || t("common.unknown");
}

/** Quest award name by award id (the game localises these at capture). */
export function awardName(id: number | null | undefined,
                          english: string | null | undefined): string {
  if (isJa() && id !== null && id !== undefined) {
    const ja = AWARDS[String(id)];
    if (ja) return ja;
  }
  return english || t("common.unknown");
}

/** Weapon class from the HunterPie enum name (`Greatsword`, `InsectGlaive`). */
export function weaponTypeName(type: string | null | undefined): string {
  if (!type || type.toLowerCase() === "unknown") return t("common.unknown");
  const key = `weapon.${type}`;
  const label = tDynamic(key);
  return label === key ? type : label;
}

/** Weapon model name captured by the mod — shown exactly as recorded. */
export function weaponModelName(name: string | null | undefined): string {
  return name || t("common.unknown");
}
