# ADR-001: Hunt Ingestion Architecture

Status: SUPERSEDED (2026-09-06) — owner scoped live feed OUT; post-hunt
dashboard only. See "Decision (post-hunt scope)" below. Phase 2 as originally
planned (real-time push API) is cancelled, not shelved.
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

### Option A — HunterPie plugin pushing over localhost: BLOCKED on 2.14

- Localhost smoke test (§0): PASS — transport assumption validated, but there
  is nothing to push from.
- Installed-build audit (cloned `HunterPie/HunterPie` @ tag `v2.14.0.466`,
  plugin surface identical tag-vs-HEAD): `IPlugin` is dead code — no assembly
  scanning, no `Plugins/`/`Modules/` loading, no manifest handling, no local
  HTTP endpoint. The plugin system is 2.15-era (`IPluginModule`,
  `plugin.manifest.json`, in-app repository) and no 2.15 host is released
  (latest release: v2.14.0.466). The v1-era `HunterPie.Plugins` examples
  (`module.json`, `Game Context`) do not apply.
- Reference TFM when unblocked: `net10.0-windows7.0` (Arisen csproj). .NET 10
  SDK ready in WSL (`~/.dotnet`, 10.0.400, dotnet-install, no sudo).
- Data availability (for when a host exists): per-player weapon YES at API
  level (`GetWeaponAsync`, nullable in schema pending live verify);
  supporters YES (map to `is_supporter`); SOS/mid-join unreliable (flags
  required, already in schema); raw/elemental/affinity YES (schema extension
  queued on frame shape); enrage/abnormality spans YES (feeds
  `monster_events`).

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

## Decision (post-hunt scope)

**Owner: no live feed needed — dashboard for reviewing completed hunts only.**
This kills the hard half of the problem (1–5s frames, buffering, WebSocket,
plugin push, CPU-overhead-during-gameplay NFR). What remains is getting ONE
structured payload per finished hunt into our DB. Selected path:

**Fork HunterPie (Apache-2.0) + quest-end local JSON dump.**
Hook `IGame.OnQuestEnd` (exists in Core), serialize the same payload HunterPie
already builds for its cloud upload, write `hunts/<quest-id>.json` to local
disk. WSL polls the folder (no watcher — `/mnt/c` doesn't fire inotify) and
imports via the already-built Phase 1 `upsert_hunt` (dedup makes re-imports
safe). Single write per hunt, no networking, no auth, no cloud.

Why this over the alternatives:
- Manual entry: no fork, but tedious per hunt and no time series (kills FR-3.3).
- Cloud download: not offered (docs list Summaries + Dashboard only, no
  export); scraping stays out (auth, tier limits, ToS).
- 2.15 plugin host: still unreleased; the fork's file dump needs no host
  support at all — it compiles against the 2.14 API we already audited.

Scope consequences:
- Phase 2 real-time API (snapshot endpoint, in-memory buffering, `<2s
  post-hunt persistence` NFR) is CANCELLED. Replaced by a file importer
  (poll dir or dashboard upload button) + import-lag target (hunt visible
  within ~1 min of quest end).
- FR-3.3 time-series curve SURVIVES if the dump includes the per-second
  frames HunterPie already plots (damage over time, monster HP, enrage
  spans) — confirm when implementing the hook; if absent, 3.3 degrades to
  per-hunt summaries and the schema columns stay nullable-ignored.
- New go/no-go (cheap): `v2.14.0.466` builds unmodified with the WSL SDK.
  VERIFIED 2026-09-06 → **GO**. Full managed compile passes (~18s, warnings
  only); all DLLs + apphost produced. Two Linux-only packaging issues, both
  with one-line fork fixes:
  1. `HunterPie.Native.vcxproj` (C++/MSVC) can't build on Linux — safe to
     skip: the host does NOT reference it and the installed app ships no
     native DLL. Build `HunterPie/HunterPie.csproj` instead of the `.sln`.
  2. The `PostBuild` target runs Windows-only `xcopy`/`del`/`rmdir` — gate it
     with `Condition="'$(OS)' == 'Windows_NT'"` in the fork.
  Recipe: `~/.dotnet` SDK 10.0.400 (dotnet-install, no sudo),
  `dotnet build HunterPie/HunterPie.csproj -c Release
  -p:EnableWindowsTargeting=true` (the flag is mandatory for Windows targets
  on Linux; our GPR token lacks `read:packages`, so the fork must avoid new
  GitHub-Packages references — build against in-solution projects only).

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
- Manual re-import path: operator re-runs saved hunt JSON files through the
  file importer (Phase 1 `upsert_hunt` dedups replays).
