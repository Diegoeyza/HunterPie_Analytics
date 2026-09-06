# ADR-001: Hunt Ingestion Architecture

Status: PROPOSED (Phase 0 spike — fill in and mark ACCEPTED or REJECTED)
Date: ________
HunterPie version tested: ________
MH Wilds game version tested: ________
.NET Runtime required: ________

## Context

Single-user local analytics over HunterPie v2 (MH Wilds). Everything downstream
(FastAPI, SQLite, Next.js) depends on one open question: how do we get
structured per-hunt data (player, weapon, monster, damage, timestamp) out of
HunterPie on Windows into WSL?

## Investigation

### Option A — HunterPie plugin pushing over localhost

- Plugin SDK reference used: ________ (`HunterPie.Plugins` example / `Arisen`)
- Plugin TFM built against: ________
- Hello-world event fired? (quest start POST to WSL `http://localhost:8000/...`): Y / N
- CPU/mem overhead during real hunt: ________
- Per-player weapon ID available for Wilds? Y / N (notes: ________)
- Supporter/NPC hunters distinguishable? Y / N

### Option B — Local export/log file polled from WSL

- Local file found? Y / N — path: ________
- Format (JSON/CSV/other) and sample attached? ________
- Reachable from WSL (`/mnt/c/...` read test)? Y / N
- Poll interval tested: ________ (no inotify/watcher — doesn't fire on `/mnt/c`)
- NOTE: HunterPie's documented Hunt Export is a cloud Accounts feature
  (tier-limited history), not a local file. If no local file exists, a cloud
  scrape is OUT for V1 (auth, tier limits, ToS) — record here, don't build it.

## Decision

Chosen: Option ________ because ________.

## Consequences

- Buffering: write-only-on-hunt-complete (simple, crash-atomic) — NOT a durable
  write-ahead buffer (see PLAN §3 Phase 2 contradiction note).
- Dedup key: HunterPie quest/session ID if available, else
  `dedup_hash` = hash(monster_id, player_ids, start_ts rounded to 1s).
- Version gating: store `hunterpie_version` + `game_version` per hunt; parser
  rejects (loudly, not silently) unknown versions.
- Untrusted inputs flagged, not merged: `is_sos`, `joined_mid_hunt`, renames.

## Fallback (HunterPie breaks after a game patch)

- Staleness alert when: ________
- Manual re-import path: ________
