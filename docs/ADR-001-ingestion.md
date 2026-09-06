# ADR-001: Hunt Ingestion Architecture

Status: BLOCKED — Windows + WSL investigation complete (2026-09-06). Neither
ingestion option works against the installed build. Do NOT build Phase 2
until one of the paths below is chosen.
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

## Decision

**No ingestion path is viable against HunterPie 2.14.0.466 — Phase 0 exits
BLOCKED, not go.** Option B rejected (no local file; cloud scrape out for V1).
Option A blocked (no plugin host). Revised paths, in recommended order:

1. **Ask upstream** (cheap, do first): open a `HunterPie/HunterPie` discussion
   asking for the 2.15 plugin-system ETA or a supported telemetry hook. Days
   vs. months changes everything; costs nothing to learn.
2. **Fork HunterPie (Apache-2.0) + built-in exporter** (self-sufficient):
   tag `v2.14.0.466` builds byte-parity with the installed app; add a minimal
   quest-end POST module next to the existing cloud upload
   (`IsHuntUploadEnabled` path); self-build with the ready WSL SDK, deploy on
   Windows. Cost: carrying a fork across game patches.
3. **Wait for 2.15 stable** (passive): plugin host + repository arrive on
   Haato's schedule; project parks until then.
4. **Descope to manual import** (fallback): hand-enter or paste post-hunt
   summaries through the Phase 1 upsert path; real-time abandoned, analytics
   survives.

Phase 2 stays shelved until a path is chosen — there is nothing to plug an
API into. Phase 1 stands as built (source-agnostic, seed-unblocked).

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
