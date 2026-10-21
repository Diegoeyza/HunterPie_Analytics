# Publishing on Nexus Mods

Nexus hosts the **in-game mod** (HuntDumper) only. The desktop app and the
HunterPie companion live on GitHub Releases — the installer is intentionally
**not** uploaded here (unsigned, and VirusTotal flagged the bundled .NET app, so
a mod-only page keeps the Lua mod clean).

## Files to upload

- **Main file:** `HuntDumper-<version>.zip` — already laid out as
  `reframework\autorun\hunt_dumper.lua` + `README.txt`. Works with Vortex and
  with a plain extract into the game folder.
- Optional: `hunt-dumper-lua.zip` — flat drop-in (script + `INSTALL.txt`).
- **Do not** upload `HunterPieAnalytics-Setup.exe`; link the GitHub Releases
  page from the description instead.

## Listing details

- **Name:** HuntDumper — Quest Awards & HP Curve Export
- **Version:** `0.11.0` (from `reframework/hunt_dumper.lua`)
- **Category:** Miscellaneous (or Utilities). REFramework Lua mods usually sit
  under Miscellaneous.
- **Requirements:** [REFramework for MH Wilds](https://github.com/praydog/REFramework) — add it as a
  requirement on the page.

### Short description

> Exports a JSON after each quest (awards, monster HP, party HP, damage totals,
> weapon) for the HunterPie Analytics dashboard. Offline, no game-file edits.

### Full description (BBCode)

```bbcode
[b][size=5]A post-hunt analytics dashboard for Monster Hunter Wilds[/size][/b]

HuntDumper records your hunts and a companion dashboard turns them into charts: DPS and clear-time trends, per-party damage curves with the monster's HP overlay, weapon breakdowns, and the 30 quest-end awards (hunter highlights). Everything runs on your own PC — no account, no cloud.

[b][size=4]Two ways to capture a hunt[/size][/b]
[list]
[*][b]REFramework mod (HuntDumper)[/b] — the in-game half. After each quest it writes one JSON to [code]reframework\data\HuntExports\[/code] with quest metadata, monster id + HP curve, per-player damage totals, party HP samples, the 30 awards, CPU-supporter flags, quest result, buffs, and your local weapon name.
[*][b]HunterPie Analytics companion[/b] — a HunterPie build with local hunt export, for per-player weapon classes and per-second DPS curves. Use either or both; the dashboard merges them.
[/list]

[b][size=4]What the dashboard shows[/size][/b]
[list]
[*][b]Progress[/b] — rolling DPS and clear-time trend over your hunts
[*][b]Damage curves[/b] — per-party DPS curves with the monster's HP and enrage markers
[*][b]Growth[/b] — how your DPS improves over time
[*][b]Highlights[/b] — the 30 quest awards with per-award leaderboards and damage share
[*][b]Survival[/b] — per-hunter HP and DPS over time with a time-in-danger summary (new in 0.11)
[*][b]Weapons, Leaderboard, High Scores, Compare, Synergy, Activity, Buffs and Review[/b] — filterable breakdowns
[/list]

[b][size=4]Requirements[/size][/b]
[list]
[*][url=https://github.com/praydog/REFramework]REFramework[/url] for Monster Hunter Wilds (required for the in-game export)
[*]Optional: the HunterPie Analytics companion, for per-player weapon classes and DPS curves
[/list]

[b][size=4]Install — REFramework side[/size][/b]
[list=1]
[*]Install REFramework for MH Wilds first.
[*]Extract HuntDumper 0.11.0 (Main file) into your game folder so you get [code]...\steamapps\common\MonsterHunterWilds\reframework\autorun\hunt_dumper.lua[/code]. (Vortex: install the archive normally.)
[*]Open the in-game REFramework menu -> HuntDumper to confirm it is enabled.
[/list]

[b][size=4]Get the dashboard + companion (optional)[/size][/b]
This mod is the in-game half of HunterPie Analytics. The Windows dashboard app and the companion are separate and live on GitHub:
[list]
[*]They install per-user (no admin) and import the JSON this mod writes.
[*]The installer bundles the dashboard, the companion and HuntDumper, and copies your existing HunterPie settings into the companion if you already use it.
[*]Launch the app, click [b]Import[/b], and click Import again after each play session.
[/list]
[url=https://github.com/Diegoeyza/HunterPie_Analytics/releases]Download the dashboard + companion[/url]

[b][size=4]Mod Organizer 2[/size][/b]
MO2 redirects writes made inside the game folder into its instance's [code]overwrite[/code] folder, so dumps land in [code]<MO2 instance>\overwrite\reframework\data\HuntExports\[/code]. The dashboard auto-detects standard MO2 instances; for a portable one, add that path under [b]Settings -> Hunt exports folders[/b], then click Import.

[b][size=4]Notes[/size][/b]
[list]
[*]Load the REFramework script before a quest starts; reloading scripts mid-hunt resets its state and skips that hunt (the next one is fine).
[*]The companion keeps up with game patches on its own — it refreshes only its offset maps, so it keeps working after a game update.
[*]The dashboard installer is not code-signed, so Windows may show "Windows protected your PC" (More info -> Run anyway). Verify downloads against [code]SHA256SUMS.txt[/code] on the releases page.
[*]The app runs locally. The only network access is an optional GitHub update check (turn it off in Settings); no hunt data is ever uploaded.
[/list]

[b][size=4]Credits[/size][/b]
[list]
[*]REFramework by praydog
[*]HunterPie by the HunterPie team (Apache-2.0)
[*]Project source: [url=https://github.com/Diegoeyza/HunterPie_Analytics]GitHub[/url] - Apache-2.0
[/list]
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
| `images/survival.png` | Survival — per-hunter HP/DPS + time in danger |
| `images/weapons.png`, `leaderboard.png`, `high-scores.png` | More tabs |
| `images/hero.png` | Montage (Progress / Curves / Growth / Highlights) |

## Permissions / credits

- Set permissions to match the license: **modifications and re-uploads allowed
  with credit** (Apache-2.0). Credit praydog (REFramework) and the HunterPie
  team in the description.
- Do not bundle REFramework itself; users install it from its own page.

## Watch-outs

- **Virus scanning / SmartScreen:** the dashboard `.exe` is **not code signed**
  (SmartScreen prompt on first run; some AV engines flag the PyInstaller
  bundle). This does not affect the Lua mod, and the installer is deliberately
  not hosted on Nexus — link the GitHub Releases page and `SHA256SUMS.txt`.
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
- [ ] Link the GitHub Releases page (no installer upload).
- [ ] Add the Nexus link to the GitHub README and vice versa.
