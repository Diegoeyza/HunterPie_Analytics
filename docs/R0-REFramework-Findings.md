# R0 — REFramework findings (MH Wilds hunt telemetry)

Status: **R0 COMPLETE** (2026-10-15). Source: live probes on REFramework
`v1.5.9.1` (game `mhwilds`), a solo 7★ Arkveld hunt.

## Verdict

REFramework exposes everything the existing importer needs for an MVP, and the
two ID namespaces match the dashboard's existing data **1:1** — so REFramework
hunts land in the same DB namespace as the HunterPie fork hunts. No ID mapping
tables required.

## Confirmed access map

| Data | Call |
|------|------|
| Quest target monster id(s) | `app.MissionManager:get_QuestDirector()` → `app.cQuestDirector:getActiveEmSet_EmIDs()` → `[27]` (all targets) |
| Quest level / stars | `cQuestDirector:getActiveQuestLv()` (7) |
| Quest cart limit | `MissionManager:get_ActiveQuestData()` → `cActiveQuestData:getQuestLife()` (3) |
| Quest time limit (min) | `cQuestDirector:getActiveTimeLimit()` / `cActiveQuestData:getTimeLimit()` (50) |
| Capture/kill condition | `cActiveQuestData:isClearConditionCapture()` / `isClearConditionKill()` |
| Arena flag | `cActiveQuestData:isArenaQuest()` |
| Reward money | `cActiveQuestData:getRewardMoney()` |
| Player's weapon at quest start | `cQuestDirector:get_Param()` → `cQuestFlowParam:get_QuestStartWeaponType()` (5) |
| Quest started time / now | `cQuestDirector:get_QuestStartedTime()`, `app.QuestUtil:getUTCTime()` (epoch secs) |
| Elapsed / remaining | `cQuestDirector:get_QuestElapsedTime()`, `get_QuestRemainTime()` |
| Live boss list | `app.QuestUtil:getActiveQuestTargetBossList()` → `app.TargetAccessKeyUtil:getEnemyCharacter(key, true)` |
| Monster HP | `EnemyCharacter:get_HealthMgr()` → `app.cHealthManager:get_Health()/get_MaxHealth()/get_HealthNormalized()` (23534.8 / 24700.0 / 0.9528) |
| Monster localized name | `app.EnemyDef.EnemyName(app.EnemyDef.ID)` (Guid → `via.gui.message.get`) |
| Player identity | `app.NetworkManager:get_UserInfoManager()` → `getUserInfoList(2)._ListInfo[i]` → `get_PlName()`, `get_ShortHunterId()`, `get_IsSelf()` (session type 2 = QUEST) |
| Player weapon (multi) | `app.PlayerManager:getQuestMembers()` → `cPlayerManageInfo:get_Character()` → `app.HunterCharacter:get_WeaponType()/get_WeaponID()` |
| Enemy context (identity/size) | `EnemyCharacter._Context` (`app.cEnemyContextHolder`) → `_Em` (`app.cEnemyContext`) → `IsMainTarget`, `GroupID`, `ModelRandomSize`, `Basic`, … |

## ID / enum mappings — both identity

- **Weapons** — `app.WeaponDef.TYPE` order equals the importer's `WEAPONS` list:
  `0 LONG_SWORD`(GS), `1 SHORT_SWORD`(SnS), `2 TWIN_SWORD`(DB), `3 TACHI`(LS),
  `4 HAMMER`, `5 WHISTLE`(HH), `6 LANCE`, `7 GUN_LANCE`, `8 SLASH_AXE`(SA),
  `9 CHARGE_AXE`(CB), `10 ROD`(IG), `11 BOW`, `12 HEAVY_BOWGUN`,
  `13 LIGHT_BOWGUN`. Emit the enum value directly as `players[].weapon`.
- **Monsters** — `app.EnemyDef.ID` equals `backend/app/data/wilds_monster_names.json`
  ids: Arkveld `27`, Guardian Arkveld `28` (`EM0160_50_0`), Doshaguma `16`,
  Guardian Doshaguma `17` (`EM0150_50_0`), Xu Wu `31`, Zoh Shia `32`, … Emit
  directly as `monsters[].id`. (Full enum dumped in `huntdumper_probe_runtime.json`.)
- Guardian/legendary variants are separate ids (e.g. `EM0150_50_0`=17) and are
  already in the names table — no variant reconstruction needed for naming.

## Data → importer-schema coverage (for R1)

| Dump field | R0 source | Status |
|-----------|-----------|--------|
| `quest.id` (external hash) | mod-generated per-session hash | TODO (R1) |
| `quest.type/level/stars/deaths/max_deaths` | quest_lv ✓; life→max_deaths ✓; type/stars best-effort | partial |
| `players[].name` / `is_hunterpie_user` | Net_QuestUserInfo name (set false) | ✓ |
| `players[].weapon` | WeaponDef.TYPE (identity) | ✓ |
| `players[].damages[]` | **not yet** — quest-award total is the proven source (per-hit frames need a damage hook) | R2 |
| `monsters[].id` | `getActiveEmSet_EmIDs()` | ✓ |
| `monsters[].max_health` | `cHealthManager.get_MaxHealth()` | ✓ |
| `monsters[].health_steps[]` | poll `get_HealthNormalized()` per frame | ✓ (R1/R2) |
| `monsters[].enrage` | not yet probed (monster_events) | R2/R3 |
| `players[].abnormalities` | not yet probed | R3 |
| `players[].gear` (raw/elem/affinity) | not yet probed (Weapon/equip types exist) | R3 |
| start/finish/uploaded timestamps | `get_QuestStartedTime` + `getUTCTime` | ✓ |

## Remaining unknown (R2)

Per-player **damage over time** for the curves. The only proven damage source is
the quest-end award total (`app.cQuestAwardSync.award04`), which
`better_hunter_highlights.lua` already reads — enough for totals, not for
per-second `damages[]`. Candidate hooks (untested): `app.EnemyCharacter.evDamage*`
/ `evHit_Damage`, or an attacker-carrying damage struct. Needs a focused probe.

## Probe artifacts

- `reframework/huntdumper_probe.lua` (repo) — v3; deployed to game `autorun/`.
- `<game>/reframework/data/huntdumper_probe_types.json` (615 KB, 43 candidate types).
- `<game>/reframework/data/huntdumper_probe_runtime.json` (live quest sample).

## R1 recommended scope (totals + HP, no per-hit frames)
Emit the importer schema with: `monsters[].id` (active em set) + `max_health` +
`health_steps[]` (polled ~1 Hz from `get_HealthNormalized`), quest metadata,
player name/weapon, and quest-end damage totals from the award sync (mirroring
`better_hunter_highlights`). That yields hunt rows, damage totals, HP curves,
clear time, and Growth — without the damage-hook work.

## R1 damage source — resolved (live hunts, 2026-10-15)

Per-player quest-end damage has two paths, both 1:1 verified against real hunts:

- **Multiplayer:** `app.cQuestFlowParam.setSharedQuestAwardInfo(userIndex,
  cQuestAwardSync)` fires per player; `cQuestAwardSync.award05` (award id 4) is
  that player's damage as a float. (This is the same path `better_hunter_highlights`
  uses — which is why that mod shows nothing in solo: solo never calls it.)
- **Solo (and self in any hunt):** `cQuestFlowParam.get_QuestAwardInfo()` returns
  `ace.UnionValue[30]` for the local player, indexed by award id; index **4** is
  the damage, stored as a packed little-endian `float32` in the union bytes
  (`Byte0..Byte3`). Verified: MULTI self = 8794.40 (== the shared-sync value);
  SOLO = 12485.9.

The `HuntDumper` mod reads both: shared sync for every player when present,
otherwise award id 4 for self. `monsters[].id` from `getActiveEmSet_EmIDs()`,
HP curve polled from `HealthNormalized`, quest lv/life/time-limit from
`cActiveQuestData`/`cQuestDirector`, self weapon from
`cQuestFlowParam.get_QuestStartWeaponType()`.

Still deferred (R2): per-player damage **over time** (per-second curves to mirror
HunterPie's live meter) — needs a play-by-play damage hook; R1 records totals.

## Weapon identity (id -> localized name)

- `app.HunterCharacter.get_WeaponID()` is a **1-based position** into that
  type's weapon array (it is *not* a 0-based index and *not* the entry's
  `_Index`). Confirmed: Whistle id 85 with an 85-entry array -> the last
  entry (`_Index` 83) = "Onyx Choros". Resolve with `list[id]` (Lua 1-based);
  fall back to an `_Index` scan only defensively.
- The localized weapon **name** (e.g. "Onyx Choros") comes from
  `app.VariousDataManager._Setting._EquipDatas._Weapon<Type>` — an
  `app.user_data.WeaponData` whose `get_Values()` is an array of
  `app.user_data.WeaponData.cData`. Each entry has `_Name` (Guid ->
  `via.gui.message.get`), `_Index` (the id), `_Attack`, `_ModelId`.
  Type→field order matches `app.WeaponDef.TYPE` (0..13).
- Verified end-to-end: a hunt with the Hunter's Horn "Onyx Choros" (Whistle,
  id 85) resolved to the localized name "Onyx Choros".
- **Decision (2026-10-16).** Per-player weapons from the mod are
  unreliable: `findPlayerInfo_MemberIndex(i)` does **not** line up with the
  dump's `userIndex` (`UserInfoList`) order, so weapons come out swapped
  (Mizutsune hunt: the HH went to the wrong hunter). Damage and per-player
  weapon **classes** therefore come from HunterPie exclusively (its
  per-player `Weapon` enum). The mod emits the weapon **name** for the
  **local player only** (`hunt_players.weapon_name`, migration v7 — the id->
  name lookup itself is reliable; only the player attribution was not). That
  name powers the hunter-scoped "Weapon name" filter (e.g. "Onyx Choros");
  HunterPie has no weapon-name field, so it can't be a HunterPie-only filter.
  HunterPie's gear fingerprints (`weapon-identities`) still power the separate
  build/variant filter.
- Cross-source authority: the mod marks its dump `source="reframework"`; hunts
  carry `hunts.source` (v6). A later HunterPie dump **refreshes** a mod-created
  hunt's core (damage/weapons/curves/quest fields) while keeping the mod's
  awards **and** its CPU-supporter flags (HunterPie lists supporters as
  normal players); a mod dump only attaches awards to an existing HunterPie
  hunt. The mod's unreliable weapons are nulled on mod-only hunts.
- Note: reloading the mod's scripts mid-hunt resets its session state, so no
  dump is written for that hunt — the mod must be loaded before quest start.
  A script reload (not a full game restart) is otherwise sufficient.

## CPU / support hunters

- `app.NpcManager.get_PartnerManager()` -> `cNpcPartnerManager.getQuestMembers()`
  enumerates NPC party entries (`cNpcPartnerManageControl`): `get_MemberIndex`,
  `get_NpcID`, `get_WeaponType`, `get_PartnerType`, `get_Valid`,
  `get_IsQuestPartner`. Invalid slots have `NpcID = -1`.
- Verified: 3 support hunters captured (Lance/LightBowgun/Lance) and imported
  with `is_supporter = 1`; handler/invalid slots filtered. NPC damage is not
  exposed via the managed API (recorded as 0).
- Names: `get_NpcID()` matches HunterPie's `Strings/Npcs/Wilds` table
  (`Npc[@Id=...]`, bundled in HunterPie's `Languages/en-us.xml`), so the mod
  bakes a small id->name map: 4=Fabius, 6=Rosso, 9=Olivia, 12=Nadia,
  15=Griffin, 17=Kai, 25=Mina, 27=Alessa, 29=Nightmist (unknown -> "NPC <id>").
  `get_PorterID()` is a different namespace (e.g. 29/27/20) and is unused.

## Hunter highlights (quest awards)

- The 30 quest-end awards (`awardId` 0..29; id 4 = damage) live on the
  `cQuestAwardSync` packet as `award01`..`award30`. `award01` is a
  `System.UInt32[4]` channel array; the rest are scalar counts. In
  multiplayer the packet arrives via `setSharedQuestAwardInfo` per
  `userIndex`; solo uses `cQuestFlowParam.get_QuestAwardInfo()` (a flat
  `ace.UnionValue[]` indexed by award id).
- Localized name/explanation/unit come from
  `app.QuestDef.Name/Explain/Unit(app.QuestDef.AwardID)` +
  `app.MessageUtil.getText(guid, 0)`; unit 1 = time (mm'ss"cc), 0 = count.
- The mod emits per-player `awards` + a top-level `awards_meta`; the importer
  stores them in `hunt_player_awards` / `awards`. Award 0 is a channel array:
  its count is the sum of the 4 channels. Verified live on a 4-player hunt
  (all 30 awards, localized names/units, damage share). HunterPie's fork
  exports no awards, so this is REFramework-only (fork hunts show no
  highlights).



