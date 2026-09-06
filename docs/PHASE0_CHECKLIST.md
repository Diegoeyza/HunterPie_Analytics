# Phase 0 — Ingestion Spike Checklist

Timebox: 3–5 calendar days. Stop on day 5 regardless and write the ADR with what was found.
Exit criteria (go/no-go): one real MH Wilds hunt captured end-to-end with
player, weapon, monster, damage, and timestamp fields populated.

## 0. Cross-boundary smoke test (do first, ~30 min) — PASS ✅

- [x] In WSL: `python3 -m http.server 8000`
- [x] From Windows (PowerShell): `curl.exe http://localhost:8000`
- [x] Result: PASS — full directory listing returned (see below).
  Localhost auto-forwarding works on this machine's WSL/Windows build.
  (Full `curl.exe` output retained below as evidence.)
 PS C:\Users\diego> curl.exe http://localhost:8000
<!DOCTYPE HTML>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Directory listing for /</title>
</head>
<body>
<h1>Directory listing for /</h1>
<hr>
<ul>
<li><a href=".git/">.git/</a></li>
<li><a href=".gitignore">.gitignore</a></li>
<li><a href=".pytest_cache/">.pytest_cache/</a></li>
<li><a href=".venv/">.venv/</a></li>
<li><a href="backend/">backend/</a></li>
<li><a href="db/">db/</a></li>
<li><a href="docs/">docs/</a></li>
<li><a href="PLAN.md">PLAN.md</a></li>
<li><a href="README.md">README.md</a></li>
</ul>
<hr>
</body>
</html>
PS C:\Users\diego>
 (if this fails, stop — the whole localhost architecture is invalid on this machine's WSL/Windows build)

## 1. Baseline HunterPie install (~1h) — DONE ✅

- [x] Install HunterPie v2 (latest, note exact version): 2.14.0.466
- [x] MH Wilds game version: latest, I think its 1.042.00.02, from steam
- [x] Confirm Damage Meter + Monster widget work in one real hunt (they do)
- [x] Record .NET Desktop Runtime version HunterPie required: **10**
  (ground truth: `C:\Program Files\HunterPie\HunterPie.runtimeconfig.json` →
  `"tfm": "net10.0"`, frameworks Microsoft.NETCore.App +
  Microsoft.WindowsDesktop.App 10.0.0. Machine has WindowsDesktop.App 8.0.3
  AND 10.0.3 installed. The FAQ saying .NET 8 is stale (dated 2022) — ignore.
  v2.14.0 changelog: ".NET 10 Migration". Plugin TFM must be net10.0 family.)

## 2. Local hunt file? (~2h) — DONE, NOT FOUND ❌ → Option B dead

- [x] Complete one Wilds quest, then search for local output:
  - HunterPie install dir (`C:\Program Files\HunterPie`): full recursive
    inventory = 42 files (exe/dlls, `.map` files, MonsterData.xml,
    AbnormalityData.xml, language xmls, themes, config.json,
    internal/account_config.json, internal/feature-flags.json).
    Zero hunt/quest/export/history artifacts.
  - `%appdata%/HunterPie`: does not exist. No HunterPie entries under
    `%LOCALAPPDATA%`. No `Plugins/` directory (nothing ever deployed).
  - `internal/account_config.json`: `IsHuntUploadEnabled: true` — corroborates
    the docs: Hunt Export = Accounts cloud feature, serialize + upload at
    quest end. No documented local file.
- [x] Local file found? **NO.**
- [x] If NOT found: cloud scraper explicitly OUT for V1 (auth, tier limits,
  ToS) — recorded in ADR-001, moving to §3.

## 3. Plugin API spike (~1–2 days) — IN PROGRESS ⏳ (references confirmed, spike open)

Concrete starting points (all confirmed to exist upstream):

- [x] `Haato3o/HunterPie.Plugins` — DamageChat, DiscordWebhook, TwitchIntegration.
- [x] `HunterPie/Arisen` — standalone plugin (ArisenPlugin.cs,
  ArisenPluginModule.cs, plugin.manifest.json). Its csproj targets
  **net10.0-windows7.0** — use that as the scaffold TFM, not
  `dotnet new classlib` defaults.
- [x] `HunterPie/deploy-plugin` — GitHub Action (action.yml + scripts).
- [x] Scaffold TFM: **net10.0-windows7.0** (from Arisen csproj + §1 runtime evidence).
- [ ] "Hello world" plugin: POST one event (e.g. quest start) to a throwaway WSL endpoint
- [ ] Copy DLL to `HunterPie/Plugins/`, confirm it loads and fires from Windows
- [ ] CPU/mem overhead during a real hunt (Task Manager / dotnet-counters): ________

⚠️ Version skew: Arisen references HunterPie.Core 2.15.0.159 / HunterPie.UI
2.15.0.181 NuGet, but the installed app is 2.14.0.466. Pin package versions
to match the installed build or expect load failures. (HunterPie was running,
PID 26304, during verification — its log file was locked.)

WSL-side preconditions (checked 2026-09-06): `dotnet` NOT installed in WSL,
and install needs an interactive sudo password — not done. To unblock:
`sudo apt update && sudo apt install -y dotnet-sdk-10.0`, then scaffold with
`-f net10.0-windows7.0`. Cross-boundary read confirmed from WSL
(`ls /mnt/c/Program\ Files/HunterPie/` works) — the DLL deploy step
(build in WSL → copy to `/mnt/c/Program Files/HunterPie/Plugins/`) is viable.

## 4. Wilds-specific data questions — ANSWERED ✅ (all five)

- [x] Per-player weapon ID exposed for Wilds? **YES at API level**
  (MHWildsPlayer.cs: `GetWeaponAsync()` / `GetPlayerWeaponAsync()`,
  per-party-member Weapon in UpdatePartyMember). Caveat: hunterpie.com shows
  no Player/Weapons widget for Wilds (World/Rise only) — read the API, not
  the widgets. Schema keeps `weapon_id` nullable in case live behavior differs.
- [x] Supporter/NPC hunters in the feed? **YES** — tracked since v2.13, v2.14
  fixed "supporter hunters not being included in hunt data exports".
  Map to `is_supporter`, exclude from FR-3.4 synergy stats.
- [x] Mid-hunt join / SOS quest behavior? **Unreliable upstream** (docs Known
  Issues: mid-hunt joins "not tracked properly", "Exported SOS quests are
  still not accurate"). `joined_mid_hunt` / `is_sos` flags required — already
  in schema, flag don't merge.
- [x] Damage split available? **YES** — v2.14 damage meter added
  raw/elemental/affinity; local config.json Wilds section has all four
  (IsRaw/IsElemental/IsAffinity/IsStatusEnabled: true). Schema extension
  (raw/elemental columns) queued for the §3 spike once the frame shape is
  known — not added speculatively.
- [x] Enrage/abnormality spans exposed? **YES** — export dashboard lists enrage
  + abnormality uptimes/spans; MonsterData.xml has AILMENT_ENRAGE (Id 0).
  Feeds `monster_events` (already in schema).

## 5. Output

- [x] Fill `docs/ADR-001-ingestion.md` — Option A (plugin push). Option B
  rejected (§2 evidence). Versions recorded.
- [x] Fallback plan if HunterPie breaks after a game patch (staleness alert +
  manual re-import — see ADR-001).
- [ ] Go / no-go signed off: ________ (PENDING — exit criteria need the §3
  spike + one live hunt end-to-end with player/weapon/monster/damage/timestamp)
