# Phase 0 — Ingestion Spike Checklist

Timebox: 3–5 calendar days. Stop on day 5 regardless and write the ADR with what was found.
Exit criteria (go/no-go): one real MH Wilds hunt captured end-to-end with
player, weapon, monster, damage, and timestamp fields populated.

## 0. Cross-boundary smoke test (do first, ~30 min)

- [ ] In WSL: `python3 -m http.server 8000`
- [ ] From Windows (PowerShell): `curl.exe http://localhost:8000`
- [ ] Result: ________ (if this fails, stop — the whole localhost architecture is invalid on this machine's WSL/Windows build)

## 1. Baseline HunterPie install (~1h)

- [ ] Install HunterPie v2 (latest, note exact version): ________
- [ ] MH Wilds game version: ________
- [ ] Confirm Damage Meter + Monster widget work in one real hunt
- [ ] Record .NET Desktop Runtime version HunterPie required (8 vs 10 — README and FAQ disagree): ________

## 2. Local hunt file? (~2h)

Do not assume a local export exists. HunterPie's documented "Hunt Export" is a
cloud Accounts feature (free tier: 7 days history), not a confirmed local file.

- [ ] Complete one Wilds quest, then search for local output:
  - HunterPie install dir
  - `%appdata%/HunterPie`
  - Any `*.json` / quest log written per hunt
- [ ] Local file found? ________ Path: ________ Format: ________
- [ ] If found: is it reachable from WSL? (`/mnt/c/...` read test — poll, don't watch; inotify doesn't fire reliably there)
- [ ] If NOT found: do not build a cloud scraper yet — note it in the ADR and move to §3

## 3. Plugin API spike (~1–2 days)

Concrete starting points (all exist upstream):

- `Haato3o/HunterPie.Plugins` — DamageChat, DiscordWebhook, TwitchIntegration examples
- `HunterPie/Arisen` — standalone plugin example
- `HunterPie/deploy-plugin` — GitHub Action for shipping plugins

- [ ] Scaffold `dotnet new classlib`, target TFM from §1: ________
- [ ] "Hello world" plugin: POST one event (e.g. quest start) to a throwaway WSL endpoint
- [ ] Copy DLL to `HunterPie/Plugins/`, confirm it loads and fires from Windows
- [ ] CPU/mem overhead during a real hunt (Task Manager / dotnet-counters): ________

## 4. Wilds-specific data questions (block schema/API if unanswered)

- [ ] Per-player weapon ID exposed for Wilds? (Wilds widget list has NO Player/Weapons widget — World/Rise only)
- [ ] Supporter/NPC hunters in the feed? (v2.13/2.14 fixed supporter inclusion — must map to `is_supporter`, not a teammate)
- [ ] Mid-hunt join / SOS quest behavior (upstream docs: "not tracked properly" / "not accurate") — confirm and plan to flag via `joined_mid_hunt` / `is_sos`
- [ ] Damage split available? (v2.14 added raw/elemental/affinity to Damage Meter)
- [ ] Enrage/abnormality spans exposed? (feeds `monster_events`, FR-3.3 phase markers)

## 5. Output

- [ ] Fill `docs/ADR-001-ingestion.md` — Option A (plugin push) or Option B (file poll), with versions recorded
- [ ] Fallback plan if HunterPie breaks after a game patch (staleness alert + manual re-import minimum)
- [ ] Go / no-go signed off: ________
