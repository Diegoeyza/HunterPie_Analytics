# Publishing on Nexus Mods

Live page: <https://www.nexusmods.com/monsterhunterwilds/mods/5158>

Nexus hosts the **in-game mod** (HuntDumper) only. The desktop app and the
HunterPie companion live on GitHub Releases — the installer is intentionally
**not** uploaded here (unsigned, and VirusTotal flagged the bundled .NET app, so
a mod-only page keeps the Lua mod clean).

## Files to upload

- **Main file:** `HuntDumper-0.12.7.zip` — already laid out as
  `reframework\autorun\hunt_dumper.lua` + `README.txt`. Works with Vortex and
  with a plain extract into the game folder.
- Optional: `hunt-dumper-lua.zip` — flat drop-in (script + `INSTALL.txt`).
- **Do not** upload `HunterPieAnalytics-Setup-*.exe`; link the GitHub Releases
  page from the description instead.

## Listing details

- **Name:** HuntDumper — Quest Awards & HP Curve Export
- **Version:** `0.12.7` (from `reframework/hunt_dumper.lua`)
- **Category:** Miscellaneous (or Utilities). REFramework Lua mods usually sit
  under Miscellaneous.
- **Requirements:** [REFramework for MH Wilds](https://github.com/praydog/REFramework) — add it as a
  requirement on the page.

### Short description

> Exports a JSON after each quest (awards, monster HP, party HP, damage totals,
> weapon) for the HunterPie Analytics dashboard. The dashboard is now bilingual
> (English / 日本語). Offline, no game-file edits.

### Full description (BBCode)

```bbcode
[b][size=5]A post-hunt analytics dashboard for Monster Hunter Wilds[/size][/b]

HuntDumper records your hunts and a companion dashboard turns them into charts: DPS and clear-time trends, per-party damage curves with the monster's HP overlay, per-hunter survival, weapon breakdowns, hunter ranks, and the 30 quest-end awards (hunter highlights). The dashboard now runs in English or Japanese. Everything runs on your own PC — no account, no cloud.

[b][size=4]New in the dashboard (1.3.0)[/size][/b]
[list]
[*][b]Japanese interface (日本語)[/b] — switch it in [b]Settings -> Display -> 言語[/b], or open the app with [code]?lang=ja[/code]. It follows your system language by default and remembers the choice; numbers, dates and durations follow it too, and charts/tables re-render the moment you switch.
[*][b]Game terminology, not machine translation[/b] — monster, skill and buff names come from the game's own Japanese text, so they read exactly like the quest results screen. The 30 quest-award names are a first pass pending native review; corrections will land in a 1.3.x patch.
[*][b]Find any hunt[/b] — the Hunts tab and the hunt manager have a search box: hunt number ([code]#1234[/code]), hunter, monster, quest, date or result, in either language.
[*][b]Buff uptime ends with the fight[/b] — the companion writes its quest clock at the results screen, which could inflate the uptime denominator by minutes. The buff window now ends at the party's last hit and still covers every recorded activation. Failed hunts keep the in-game timer.
[*][b]Older companion dumps are repaired on re-import[/b] — previously-unknown quest targets get their identity filled in, so "Only quest objectives" works retroactively instead of hiding the wrong hunts.
[/list]

[b][size=4]New in HuntDumper 0.12.7[/size][/b]
[list]
[*][b]Party HP attribution fixed.[/b] Each hunter's HP series is keyed by the game's NetworkManager user index — the same index the quest roster and the quest award sync use. 0.12.6 used the _PlayerList control slot, and 0.12.5 used quest/join order; both can permute against the roster on a live hunt, which could show one hunter's near-death curve under another hunter's name.
[*][b]One identity for HP, names and awards.[/b] The self entry, the roster names, the HP series and the award/damage lookup now all use that user index, so a hunter cannot be split across two identities.
[*][b]Roster capture.[/b] Names and member indices are captured at quest start and refreshed during the hunt, covering SOS joins and lobby slot permutations.
[*][b]HP map audit.[/b] With Debug logging enabled, the mod writes one hp map line per hunter (user index, name, control slot, series end and live HP) and logs a warning if they disagree. If a future game update changes the identity order, one dump is enough to see it.
[/list]

[b][size=4]New in the dashboard (1.2.6)[/size][/b]
[list]
[*][b]Hunter rank.[/b] Each hunter's HR is shown next to their name in the hunt party cards and the Hunters tooltip. It is read from the HunterPie Analytics companion's party export — HuntDumper itself does not capture rank.
[*][b]Corrected HP in the charts.[/b] The dashboard stores the 0.12.7 series and keeps them when the companion and mod dumps for the same quest are merged.
[*][b]Mid-hunt companion restarts.[/b] A companion restarted during a quest is now merged back into the same hunt instead of creating a duplicate with no HP.
[/list]

[b][size=4]New in 0.12.0[/size][/b]
[list]
[*][b]Buffs are companion-only.[/b] The mod no longer exports buffs. Consumable, song, debuff and skill uptime now comes from the HunterPie Analytics companion, which also covers skill windows the mod never tracked.
[/list]

[b][size=4]New in 0.11.0[/size][/b]
[list]
[*][b]Survival.[/b] Per-hunter HP and DPS on one timeline, with min/avg HP and time spent below 50%/25% or at full HP.
[*]Quest result detection (clear / fail / time-up) instead of relying only on cart count.
[*]More reliable party HP mapping for SOS hunts, plus corrected HP/DPS timeline alignment.
[/list]

[b][size=4]Two ways to capture a hunt[/size][/b]
[list]
[*][b]REFramework mod (HuntDumper)[/b] — the in-game half. After each quest it writes one JSON to [code]reframework\data\HuntExports\[/code] with quest metadata, monster id + HP curve, per-player damage totals, party HP samples, quest result, the 30 awards, CPU-supporter flags, and your local weapon name.
[*][b]HunterPie Analytics companion[/b] — a HunterPie build with local hunt export, for per-player weapon classes, per-second DPS curves and hunter ranks. Use either or both; the dashboard merges them.
[/list]

[b][size=4]What the dashboard shows[/size][/b]
[list]
[*][b]Progress[/b] — rolling DPS and clear-time trend over your hunts.
[*][b]Damage curves[/b] — per-party DPS curves with the monster's HP and enrage markers.
[*][b]Growth[/b] — how your DPS improves over time.
[*][b]Highlights[/b] — the 30 quest awards with per-award leaderboards and damage share.
[*][b]Hunts[/b] — every run, newest first, with search by hunt #, hunter, monster, quest, date or result.
[*][b]Survival[/b] — per-hunter HP and DPS over time with a time-in-danger summary. Requires HuntDumper 0.11+; correct party attribution requires 0.12.7+.
[*][b]Weapons, Leaderboard, High Scores, Compare, Synergy, Activity, Buffs and Review[/b] — filterable breakdowns.
[/list]

[b][size=4]Requirements[/size][/b]
[list]
[*][url=https://github.com/praydog/REFramework]REFramework[/url] for Monster Hunter Wilds (required for the in-game export).
[*]Optional: the HunterPie Analytics companion, for per-player weapon classes, DPS curves and hunter ranks.
[/list]

[b][size=4]Install — REFramework side[/size][/b]
[list=1]
[*]Install REFramework for MH Wilds first.
[*]Extract HuntDumper 0.12.7 (Main file) into your game folder so you get [code]...\steamapps\common\MonsterHunterWilds\reframework\autorun\hunt_dumper.lua[/code]. (Vortex: install the archive normally.)
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

[b][size=4]Mod Organizer 2 (Skip this section if not using it)[/size][/b]
MO2 redirects writes made inside the game folder into its instance's [code]overwrite[/code] folder, so dumps land in [code]<MO2 instance>\overwrite\reframework\data\HuntExports\[/code]. The dashboard auto-detects standard MO2 instances; for a portable one, add that path under [b]Settings -> Hunt exports folders[/b], then click Import.

[b][size=4]Notes[/size][/b]
[list]
[*]Use HuntDumper 0.12.7 or newer for correct party HP and Survival. 0.11+ still exports awards and the monster HP curve, but party HP can be assigned to the wrong hunter.
[*]Hunts recorded with older versions keep the mapping they were recorded with; re-record a hunt with 0.12.7 to get the corrected party HP.
[*]Hunter ranks appear for hunts recorded with the updated companion; older dumps without rank stay blank.
[*]Buffs (consumable/skill/song/debuff uptime) require the companion — the mod has not exported them since 0.12.0.
[*]The Japanese UI is a first pass: the interface, monster and skill names are reviewed for terminology, quest-award names are pending a native reviewer. Send corrections and they will ship in a 1.3.x patch.
[*]Load the REFramework script before a quest starts; reloading scripts mid-hunt resets its state and skips that hunt (the next one is fine).
[*]The companion keeps up with game patches on its own — it refreshes only its offset maps, so it keeps working after a game update.
[*]The dashboard installer is not code-signed, so Windows may show "Windows protected your PC" (More info -> Run anyway). Verify downloads against [code]SHA256SUMS.txt[/code] on the releases page.
[*]The app runs locally. The only network access is an optional GitHub update check (turn it off in Settings); no hunt data is ever uploaded.
[*]When a desktop app update needs a newer HuntDumper build, the app shows a "Mod vX -> reinstall" notice with instructions.
[/list]

[b][size=4]Credits[/size][/b]
[list]
[*]REFramework by praydog
[*]HunterPie by the HunterPie team (Apache-2.0)
[*]Japanese game terminology from the game's own text via HunterPie's localization files (MIT); [url=https://mhwilds.kiranico.com/ja]kiranico[/url] for cross-checking
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
| `images/hunts.png` | Hunts — every run, searchable |
| `images/survival.png` | Survival — per-hunter HP/DPS + time in danger |
| `images/weapons.png`, `leaderboard.png`, `high-scores.png` | More tabs |
| `images/hero.png` | Montage (Progress / Curves / Growth / Highlights) |

For 1.3.0, add one screenshot of the Japanese UI (e.g. the Hunts tab or the
Buffs table at `?lang=ja`); the review-sheet run already produces them under
`/tmp/opencode/e2e/` locally.

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
  the GitHub release tag. The Lua mod is unchanged in 1.3.0 (still 0.12.7), so
  the Nexus *file* stays as-is; only the description changes.
- **Keep the pages linked:** add the Nexus URL to the GitHub README and the
  GitHub release URL to the Nexus description.

## Checklist

- [x] Build `HuntDumper-0.12.7.zip` (release asset).
- [x] Create the MH Wilds mod page; upload the main file.
- [x] Add REFramework as a requirement.
- [ ] Paste the 1.3.0 description; set credits and permissions.
- [ ] Add one Japanese-UI gallery screenshot.
- [x] Link the GitHub Releases page (no installer upload).
- [x] Add the Nexus link to the GitHub README and vice versa.
