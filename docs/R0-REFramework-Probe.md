# R0 — REFramework probe runbook

Goal: discover which game types/methods REFramework can expose, so the
permanent `hunt_dumper.lua` (R1) is written against real names instead of guesses.

## What exists already (evidence from installed mods)

- REFramework **v1.5.9.1** loaded in the MH Wilds game dir via `dinput8.dll`.
- `_CatLib` (shared framework) already wraps useful APIs:
  - `GetQuestBossList()` -> `app.QuestUtil.getActiveQuestTargetBossList()` +
    `app.TargetAccessKeyUtil.getEnemyCharacter(key, true)` -> `app.EnemyCharacter`.
  - quest hooks: `app.cQuestPlaying.enter()/exit()`, `app.cQuestReward.enter()`,
    `app.cQuestClearEnd.enter()`.
  - quest time: `app.cQuestDirector.get_QuestElapsedTime()/getActiveTimeLimit()`.
- `better_hunter_highlights.lua` proves, at quest end:
  - `app.NetworkManager` -> `get_UserInfoManager()` -> QUEST session members with
    `get_PlName()`, `get_ShortHunterId()`, `get_IsSelf()`;
  - `app.cQuestAwardSync` carries per-player damage (award 4) + 30 award counts.

Unknowns R0 must resolve: monster **HP / max / id / variant / crown**, per-player
**weapon**, **quest id/type/stars/deaths**, and any **live damage** source for
per-second `damages[]` frames + `health_steps[]`.

## Files

| Where | What |
|-------|------|
| `reframework/huntdumper_probe.lua` (this repo) | source of truth |
| `<game>/reframework/autorun/huntdumper_probe.lua` | deployed copy REFramework runs |

Re-deploy after edits:

```sh
cp reframework/huntdumper_probe.lua \
  "/mnt/c/Program Files (x86)/Steam/steamapps/common/MonsterHunterWilds/reframework/autorun/huntdumper_probe.lua"
```

## Run it

1. Launch MH Wilds (REFramework loads the probe on boot; if the game was already
   running, open the REFramework menu and reload scripts / restart).
2. Open the REFramework menu -> **HuntDumper Probe (R0)**.
3. Click **Dump types** (works in the hub or in a quest).
4. Load into a quest with monsters alive, land a few hits, then click
   **Sample runtime** (mid-hunt is best; a couple of seconds is enough).
5. Results:
   - `<game>/reframework/data/huntdumper_probe_types.json`
   - `<game>/reframework/data/huntdumper_probe_runtime.json`

WSL can read them directly at
`/mnt/c/Program Files (x86)/Steam/steamapps/common/MonsterHunterWilds/reframework/data/`.

## What the probe reports

- **types**: for a curated list of candidate types (quest, enemy, player, network,
  damage/health) -> whether each exists, plus every field (name/type/static) and
  method (name/full signature/return type).
- **runtime**: current quest timing; the active quest target boss list with a
  full field dump + HP/health/life getters per `EnemyCharacter`; and the QUEST
  session members with identity fields.

## After running

The findings get distilled into `docs/ADR-002-reframework-ingestion.md` and drive
R1 (`hunt_dumper.lua`). Delete the probe from `autorun/` once R0 is closed.
