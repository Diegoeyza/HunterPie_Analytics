# ADR-001: Hunt Ingestion Architecture

Status: INTERIM — Windows investigation complete (2026-09-06), §3 spike + live
hunt still open. Promote to ACCEPTED when the exit criteria is met
(one real hunt end-to-end with player/weapon/monster/damage/timestamp).
Date: 2026-09-06
HunterPie version tested: 2.14.0.466 (FileVersion confirmed, running PID 26304)
MH Wilds game version tested: 1.042.00.02 (Steam; on-disk map MonsterHunterWilds.1.42.0.2.map)
.NET Runtime required: 10 (HunterPie.runtimeconfig.json: `"tfm": "net10.0"`,
Microsoft.NETCore.App + Microsoft.WindowsDesktop.App 10.0.0; the FAQ claiming
.NET 8 is stale, dated 2022 — ignore it)

## Context

Single-user local analytics over HunterPie v2 (MH Wilds). Everything downstream
(FastAPI, SQLite, Next.js) depends on one open question: how do we get
structured per-hunt data (player, weapon, monster, damage, timestamp) out of
HunterPie on Windows into WSL?

## Investigation

### Option A — HunterPie plugin pushing over localhost: SELECTED (pending spike)

- Localhost smoke test (§0): PASS — `curl.exe http://localhost:8000` from
  PowerShell returned the full WSL directory listing. Auto-forwarding works on
  this machine's build. The transport assumption is validated.
- Plugin SDK references (all confirmed to exist):
  - `Haato3o/HunterPie.Plugins` (DamageChat, DiscordWebhook, TwitchIntegration)
  - `HunterPie/Arisen` (ArisenPlugin.cs, ArisenPluginModule.cs, plugin.manifest.json)
  - `HunterPie/deploy-plugin` (action.yml + scripts)
- Plugin TFM: **net10.0-windows7.0** (from Arisen csproj — do NOT use
  `dotnet new classlib` defaults).
- ⚠️ Version skew: Arisen references HunterPie.Core 2.15.0.159 / HunterPie.UI
  2.15.0.181 NuGet, but the installed app is 2.14.0.466. Pin package versions
  to the installed build or expect load failures.
- Hello-world POST / DLL load / CPU-mem overhead: OPEN (needs §3 spike + hunt).
- Per-player weapon ID for Wilds: YES at API level (MHWildsPlayer.cs:
  `GetWeaponAsync()` / `GetPlayerWeaponAsync()`, per-party-member Weapon).
  Caveat: no Player/Weapons widget for Wilds (World/Rise only) — trust the API,
  verify live. Schema keeps `weapon_id` nullable.
- Supporter/NPC hunters: tracked since v2.13; v2.14 fixed their exclusion from
  hunt exports. Map to `is_supporter`, exclude from synergy stats.
- Damage split: available (v2.14 raw/elemental/affinity; local config.json
  Wilds section has all four enabled). Schema extension queued for the §3 spike
  once the frame shape is known — not added speculatively.
- Enrage/abnormality spans: available (export dashboard + MonsterData.xml
  AILMENT_ENRAGE Id 0). Feeds `monster_events`.

### Option B — Local export/log file polled from WSL: REJECTED

- Full recursive inventory of `C:\Program Files\HunterPie` = 42 files
  (exe/dlls, `.map` files, MonsterData.xml, AbnormalityData.xml, language
  xmls, themes, config.json, internal/account_config.json,
  internal/feature-flags.json). Zero hunt/quest/export/history artifacts.
- `%APPDATA%\HunterPie` does not exist; nothing under `%LOCALAPPDATA%`;
  no `Plugins/` directory.
- `internal/account_config.json`: `IsHuntUploadEnabled: true` — Hunt Export is
  an Accounts cloud feature (free tier: 7 days), serialize + upload at quest
  end. There is no local file to poll.
- Cloud scrape explicitly OUT for V1 (auth, tier limits, ToS). Not revisited
  without a new ADR.

## Decision

**Option A (plugin push over localhost).** Option B is rejected on evidence,
not on suspicion. All schema/API work proceeds on the assumption that a
net10.0-windows7.0 plugin reads HunterPie's in-memory Wilds API and POSTs to
the WSL-hosted FastAPI server — until the §3 spike confirms or kills it.

## Consequences

- Buffering: write-only-on-hunt-complete (simple, crash-atomic) — NOT a durable
  write-ahead buffer (see PLAN §3 Phase 2 contradiction note).
- Dedup key: HunterPie quest/session ID if available, else
  `dedup_hash` = hash(monster_id, player_ids, start_ts rounded to 1s).
- Version gating: store `hunterpie_version` + `game_version` per hunt; parser
  rejects (loudly, not silently) unknown versions.
- Untrusted inputs flagged, not merged: `is_sos`, `joined_mid_hunt`, renames.
  Upstream Known Issues confirm both are unreliable ("not tracked properly",
  "still not accurate").
- Phase 1 schema already covers every §4 answer (nullable `weapon_id`,
  `is_supporter`, both flags, `monster_events`, version columns). Only the
  raw/elemental split awaits the frame shape.

## Fallback (HunterPie breaks after a game patch)

- Staleness alert: after each Wilds patch, compare the installed
  `Address/MonsterHunterWilds.*.map` max version against the game version;
  on mismatch, surface "HunterPie version unsupported by our parser" and halt
  ingestion loudly instead of ingesting garbage.
- Manual re-import path: operator replays saved hunt payloads through
  `POST /telemetry/hunt-complete` once a compatible HunterPie ships
  (endpoint to be built in Phase 2; Phase 1 `upsert_hunt` dedups replays).
