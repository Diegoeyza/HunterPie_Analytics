# Publishing on Nexus Mods

Nexus is a good home for the **in-game mod** (HuntDumper). The desktop app is a
companion tool — you can add it as a secondary file on the same page, or as a
separate "Utilities" mod page. This file is a copy-paste kit.

## File to upload

Build it with `./package.sh` or grab it from a release:

- **Main file:** `HuntDumper-<version>.zip` — already laid out as
  `reframework\autorun\hunt_dumper.lua` + `README.txt`. Works with Vortex and
  with a plain extract into the game folder.

Optional secondary files:

- `hunt-dumper-lua.zip` — flat drop-in (script + `INSTALL.txt`).
- `HunterPieAnalytics-Setup-<ver>.exe` — the dashboard (mark it as optional;
  see the SmartScreen note below). It bundles the REFramework mod, the
  GETTING_STARTED guide, and the **HunterPie Analytics companion** (HunterPie +
  local export) with its own Start Menu shortcut. Users who already run
  standard HunterPie need the companion — stock HunterPie does not export hunt
  data.

## Listing details

- **Name:** HuntDumper — Quest Awards & HP Curve Export
- **Version:** `<version>` (from `reframework/hunt_dumper.lua`)
- **Category:** Miscellaneous (or Utilities). REFramework Lua mods usually sit
  under Miscellaneous.
- **Requirements:** [REFramework for MH Wilds](https://www.nexusmods.com/monsterhunterwilds/mods/) — add it as a
  requirement link on the page.

### Short description

> Exports a JSON after each quest (awards, HP curve, damage totals, weapon) so
> you can graph your hunts in the companion analytics dashboard. No network, no
> game-file edits.

### Full description (BBCode-friendly)

```text
[b]What it does[/b]
At quest end, HuntDumper writes one JSON file to
[code]reframework\data\HuntExports\[/code] containing:
[list]
[*]quest metadata (id, type, stars, deaths)
[*]monster id + max HP and the polled HP curve
[*]per-player damage totals
[*]the 30 quest awards (hunter highlights)
[*]CPU-supporter flags and your local player's weapon name
[/list]
It never modifies game data and never talks to the network.

[b]Requirements[/b]
REFramework for Monster Hunter Wilds (install it first).

[b]Installation[/b]
Vortex: install the archive normally.
Manual: extract into your game folder so you get
[code]<game>\reframework\autorun\hunt_dumper.lua[/code]
(default Steam path: [code]...\steamapps\common\MonsterHunterWilds\[/code]).

Open the in-game REFramework menu -> HuntDumper to confirm it is enabled.

[b]Notes[/b]
Load the script before a quest starts. Reloading scripts mid-hunt resets its
state, so that hunt is skipped (the next one is fine). This mod does not capture
per-player weapon classes or DPS curves - those come from HunterPie.

[b]Companion dashboard[/b]
This mod is one half of a post-hunt analytics dashboard (damage, DPS curves,
awards, comparisons). See the project releases page linked here.

[b]Credits[/b]
REFramework by praydog. HunterPie by the HunterPie team (Apache-2.0). This
project is Apache-2.0.
```

## Gallery images

Ready-to-upload screenshots live in [`images/`](images/) (1440×900, PNG).
Use them as the mod-page gallery; `hero.png` is a 2×2 montage for the header.

| File | Tab |
|------|-----|
| `images/progress.png` | Progress — rolling DPS + clear-time trend |
| `images/curves.png` | Damage curves — per-party curves, HP overlay, enrage |
| `images/highlights.png` | Highlights — the 30 quest awards + damage share |
| `images/growth.png` | Growth — DPS improvement over time |
| `images/hunts.png` | Hunts — every run, expandable |
| `images/weapons.png`, `quests.png`, `leaderboard.png`, `high-scores.png` | More tabs |
| `images/hero.png` | Montage (Progress / Curves / Growth / Highlights) |

## Permissions / credits

- Set permissions to match the license: **modifications and re-uploads allowed
  with credit** (Apache-2.0). Credit praydog (REFramework) and the HunterPie
  team in the description.
- Do not bundle REFramework itself; users install it from its own page.

## Watch-outs

- **Virus scanning / SmartScreen:** the optional dashboard `.exe` is **not code
  signed**, so Windows will show a SmartScreen prompt on first run (and some AV
  may flag it). Say so plainly, point users to the Store build, and link
  `SHA256SUMS.txt`. This does not affect the Lua mod itself.
- **No monetization:** Nexus forbids paywalling; keep everything free.
- **Versioning:** keep the Nexus file version in sync with the Lua `VERSION` and
  the GitHub release tag.
- **Keep the pages linked:** add the Nexus URL to the GitHub README and the
  GitHub release URL to the Nexus description.

## Checklist

- [ ] Build `HuntDumper-<version>.zip` (`./package.sh` or from a release).
- [ ] Create the MH Wilds mod page; upload the main file.
- [ ] Add REFramework as a requirement.
- [ ] Paste the description; set credits and permissions.
- [ ] (Optional) attach the dashboard installer as a secondary file.
- [ ] Add the Nexus link to the GitHub README and vice versa.
