#!/usr/bin/env node
/** Locale parity gate (CI + local `npm run check:i18n`).
 *
 *  The dictionaries are JSON so several people/agents can extend them without
 *  merge conflicts, which means `tsc` alone can't catch a key that exists only
 *  in English. This script compares every area file pairwise and reports:
 *    - keys missing from a translation
 *    - keys that only exist in a translation
 *    - empty values
 *  Exits non-zero on any problem.
 */
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const localesDir = join(root, "locales");
const source = "en";
const targets = ["ja"];

const files = readdirSync(join(localesDir, source))
  .filter((name) => name.endsWith(".json"))
  .sort();

const read = (locale, name) =>
  JSON.parse(readFileSync(join(localesDir, locale, name), "utf8"));

const problems = [];
let keyCount = 0;

for (const name of files) {
  const english = read(source, name);
  keyCount += Object.keys(english).length;
  for (const [key, value] of Object.entries(english)) {
    if (!String(value).trim()) problems.push(`${source}/${name}: "${key}" is empty`);
  }
  for (const locale of targets) {
    let translated;
    try {
      translated = read(locale, name);
    } catch {
      problems.push(`${locale}/${name}: file missing`);
      continue;
    }
    for (const key of Object.keys(english)) {
      if (!(key in translated)) problems.push(`${locale}/${name}: missing "${key}"`);
      else if (!String(translated[key]).trim()) problems.push(`${locale}/${name}: "${key}" is empty`);
    }
    for (const key of Object.keys(translated)) {
      if (!(key in english)) problems.push(`${locale}/${name}: extra "${key}" (not in ${source})`);
    }
    // Placeholders must survive translation: {n}, {hunts}, ...
    for (const key of Object.keys(english)) {
      const expected = new Set(String(english[key]).match(/\{\w+\}/g) ?? []);
      const got = new Set(String(translated[key] ?? "").match(/\{\w+\}/g) ?? []);
      for (const token of expected) {
        if (!got.has(token)) problems.push(`${locale}/${name}: "${key}" lost placeholder ${token}`);
      }
    }
  }
}

// Duplicate keys inside a file are silently swallowed by JSON.parse.
for (const locale of [source, ...targets]) {
  for (const name of files) {
    const text = readFileSync(join(localesDir, locale, name), "utf8");
    const seen = new Set();
    for (const m of text.matchAll(/^\s*"([^"]+)"\s*:/gm)) {
      if (seen.has(m[1])) problems.push(`${locale}/${name}: duplicate key "${m[1]}"`);
      seen.add(m[1]);
    }
  }
}

// Source scan: a literal key used in code must exist in English. Dynamic
// families (`weapon.${type}`) are skipped, they are guarded at the call site.
const enKeys = new Set();
for (const name of files) for (const k of Object.keys(read(source, name))) enKeys.add(k);
// Key prefixes (`hunts.`, `views.`) are not the same as the area file names,
// so match on the key namespace itself.
const areas = new Set([...enKeys].map((k) => k.split(".")[0]));
const sourceDirs = ["app", "components", "lib"];
const KEY_LIKE = /"([a-z][A-Za-z0-9]*(?:\.[A-Za-z0-9_-]+)+)"/g;
function walk(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(entry.name)) out.push(full);
  }
  return out;
}

for (const dir of sourceDirs) {
  for (const file of walk(join(root, dir))) {
    const text = readFileSync(file, "utf8");
    for (const m of text.matchAll(KEY_LIKE)) {
      const key = m[1];
      const area = key.split(".")[0];
      if (!areas.has(area)) continue;
      if (!enKeys.has(key)) problems.push(`${file.replace(root + "/", "")}: unknown key "${key}"`);
    }
  }
}

if (problems.length > 0) {
  console.error(`i18n check failed (${problems.length}):`);
  for (const p of problems) console.error(`  - ${p}`);
  process.exit(1);
}
console.log(`i18n OK — ${files.length} areas, ${keyCount} keys, ${targets.length} translation(s)`);
