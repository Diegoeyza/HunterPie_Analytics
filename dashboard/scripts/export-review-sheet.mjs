#!/usr/bin/env node
/** Export the translation review sheet for a native reviewer.
 *
 *  Reads the dictionaries and writes:
 *    docs/i18n/japanese-review.md   — grouped by screen area, EN | JA
 *    docs/i18n/japanese-review.csv  — same content for spreadsheet comments
 *
 *  Usage: `npm run i18n:sheet` (from dashboard/) writes the files;
 *  `npm run i18n:sheet -- --check` fails when they are stale (CI-safe).
 *  This file is generated — corrections come back as comments/copies, not
 *  in-place edits, so regenerating never destroys reviewer work.
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const dashboard = join(dirname(fileURLToPath(import.meta.url)), "..");
const repo = join(dashboard, "..");
const outDir = join(repo, "docs", "i18n");

const AREAS = {
  common: "App shell, top bar, data-source note, generic buttons",
  tabs: "Tab names and one-line descriptions",
  scope: "Hunter scope bar, party filter, weapon/build pickers",
  settings: "Settings dialog, update pill, mod pill, What's new",
  table: "Tables, filters, empty states, dialogs, toasts, charts, hunt manager",
  "views.progress": "Progress tab",
  "views.growth": "Growth tab",
  "views.weapons": "Weapons tab",
  "views.highlights": "Highlights tab",
  "views.curves": "Damage curves tab",
  "views.hunts": "Hunts tab",
  "views.survival": "Survival tab",
  "views.leaderboard": "Leaderboard tab",
  "views.highscores": "High scores tab",
  "views.compare": "Compare tab",
  "views.activity": "Activity tab",
  "views.synergy": "Synergy tab",
  "views.buffs": "Buffs tab",
  names: "Weapon classes and shared labels",
};

const read = (locale, name) =>
  JSON.parse(readFileSync(join(dashboard, "locales", locale, `${name}.json`), "utf8"));

const areas = Object.keys(AREAS).filter((name) =>
  readdirSync(join(dashboard, "locales", "en")).includes(`${name}.json`));

const esc = (s) => String(s).replace(/\|/g, "\\|").replace(/\n/g, " ");
const csvEsc = (s) => `"${String(s).replace(/"/g, '""')}"`;

const checkOnly = process.argv.includes("--check");

const md = [];
md.push("# Japanese translation review sheet");
md.push("");
md.push("**Generated file — do not edit in place** (`npm run i18n:sheet` overwrites it).");
md.push("Review by commenting in the PR/issue, or copy the CSV, fill the `japanese` and");
md.push("`source` columns, and send it back.");
md.push("");
md.push("Source: `dashboard/locales/*/` — English is the source of truth for keys.");
md.push("Flag anything that reads unnaturally in the game's own vocabulary. Placeholders");
md.push("like `{n}` are filled by the app and must stay in the string.");
md.push("");
md.push("Terminology source for data names: the game's own text (monsters and skills) and");
md.push("kiranico (verification). Quest award names are a literal first pass and most need your review.");
md.push("");

const csv = [["area", "key", "english", "japanese", "source"].map(csvEsc).join(",")];

let total = 0;
for (const name of areas) {
  const en = read("en", name);
  const ja = read("ja", name);
  const keys = Object.keys(en);
  if (keys.length === 0) continue;
  total += keys.length;
  md.push(`## ${AREAS[name]}`);
  md.push(`<sub>locales/*/${name}.json · ${keys.length} strings</sub>`);
  md.push("");
  md.push("| key | English | 日本語 | source |");
  md.push("| --- | --- | --- | --- |");
  for (const key of keys) {
    md.push(`| \`${key}\` | ${esc(en[key])} | ${esc(ja[key] ?? "MISSING")} |  |`);
    csv.push([name, key, en[key], ja[key] ?? "", ""].map(csvEsc).join(","));
  }
  md.push("");
}

// Checked-in hand-written data names (awards). The English column is the name
// the game wrote at capture time, so the reviewer sees what each translation
// is meant to replace.
const AWARD_EN = {
  0: "Support All-Star", 1: "Ailment Master", 2: "Dizzy Pro",
  3: "Target Destroyer", 4: "Established Hunter", 5: "Master Mounter",
  6: "Treasure Hunter", 7: "Field Researcher", 8: "Slinger Sniper",
  9: "Survival Expert", 10: "Tool Specialist", 11: "BBQ King",
  12: "Master Angler", 13: "Beast Master", 14: "Stealth Hunter",
  15: "Gathering Maniac", 16: "Item Addict", 17: "Obsessed Observer",
  18: "Hit 'Em Where It Hurts!", 19: "Beautiful Bombardier",
  20: "Social Butterfly", 21: "Small Game Monster Hunter",
  22: "Slinger Savant", 23: "Seikret Sidestep", 24: "Perfect Counters",
  25: "Glide Master", 26: "Dual Wielder", 27: "Assassination",
  28: "Weak Point", 29: "Clasher",
};

try {
  const data = JSON.parse(readFileSync(join(dashboard, "locales", "ja", "data.json"), "utf8"));
  const awards = data.awards ?? {};
  if (Object.keys(awards).length > 0) {
    md.push("## Quest awards (literal first pass — needs review)");
    md.push("");
    md.push("Please replace the 日本語 column with the wording on the quest results screen.");
    md.push("Award names are keyed by id, so a correction also applies to past hunts.");
    md.push("");
    md.push("| id | English (captured) | 日本語（初版） | your correction |");
    md.push("| --- | --- | --- | --- |");
    for (const [id, ja] of Object.entries(awards)) {
      md.push(`| ${id} | ${esc(AWARD_EN[id] ?? "")} | ${esc(ja)} |  |`);
      csv.push(["award", id, AWARD_EN[id] ?? "", ja, "literal first pass"].map(csvEsc).join(","));
    }
    md.push("");
  }
} catch { /* awards not generated yet */ }

const mdPath = join(outDir, "japanese-review.md");
const csvPath = join(outDir, "japanese-review.csv");
const mdOut = md.join("\n");
const csvOut = csv.join("\n");

if (checkOnly) {
  const stale = [
    !existsSync(mdPath) || readFileSync(mdPath, "utf8") !== mdOut ? "japanese-review.md" : null,
    !existsSync(csvPath) || readFileSync(csvPath, "utf8") !== csvOut ? "japanese-review.csv" : null,
  ].filter(Boolean);
  if (stale.length > 0) {
    console.error(`review sheet is stale: ${stale.join(", ")} — run npm run i18n:sheet`);
    process.exit(1);
  }
  console.log(`review sheet is up to date — ${total} strings`);
} else {
  mkdirSync(outDir, { recursive: true });
  writeFileSync(mdPath, mdOut);
  writeFileSync(csvPath, csvOut);
  console.log(`wrote docs/i18n/japanese-review.{md,csv} — ${total} UI strings in ${areas.length} areas`);
}
