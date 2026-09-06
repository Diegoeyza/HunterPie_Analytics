# MH Wilds Telemetry & Progress Analytics — Project Plan

## 0. Purpose of this document
Translate the PRD into a buildable, milestone-based plan: architecture decisions, schema, phased delivery, and the risks that could sink the project if not addressed early.

---

## 1. Guiding Principle: De-risk the data source first

Everything downstream (schema, API, dashboard) is standard, well-understood engineering. The one genuinely uncertain piece is **FR-1 (data ingestion from HunterPie)**. As of early 2026, HunterPie v2 has active, ongoing Monster Hunter Wilds support (damage meter with per-second DPS plotting, synced across party members, updated alongside game patches). That's encouraging, but we do **not** yet know:

- Whether HunterPie v2 exposes a documented **plugin SDK** we can hook into, vs. only internal/undocumented internals.
- Whether there's a **local WebSocket/event stream** we can subscribe to, or whether we're limited to reading exported log/JSON files after each quest.
- How **stable** the memory offsets are release-to-release (HunterPie ships frequent "add support to vX.XX.X" patches — this affects how often our ingestion breaks).

**Decision: Phase 0 is a throwaway spike, not part of the committed schedule, whose sole output is a go/no-go on ingestion architecture.** Nothing else starts until Phase 0 concludes.

---

## 2. Architecture (as proposed, pending Phase 0 confirmation)

```
──────────── Windows ────────────  │  ──────────── WSL2 ────────────
                                    │
[ Monster Hunter Wilds ]           │
         │                         │
         ▼                         │
[ HunterPie v2 + our plugin ]      │
         │  Option A: WebSocket/HTTP push over localhost ──────►  [ Ingestion API — FastAPI ]
         │  Option B: export/log file, polled  ────────────────►  │  - schema validation (pydantic)
                                    │                              │  - idempotent upsert
                                    │                              ▼
                                    │                     [ Database — SQLite, ext4-native path ]
                                    │                              │
                                    │                              ▼
                                    │                     [ Web Dashboard — Next.js + Recharts ]
                                    │                              │
                                    ▼                              ▼
                         [ Windows browser: localhost:3000 opens the WSL-hosted dashboard ]
```

**Dev environment split (WSL for code, Windows for HunterPie):**
- All application code — FastAPI, SQLAlchemy models, Next.js dashboard — is written, run, and version-controlled inside WSL. Nothing about this changes vs. a normal Linux dev setup.
- HunterPie.exe itself must run natively on Windows (it reads MH Wilds' process memory directly, and MH Wilds is a Windows/Steam game) — this isn't optional and doesn't change regardless of ingestion option.
- **Networking:** current WSL2 builds auto-forward `localhost` both directions, so a Windows process (HunterPie / our plugin) can `POST http://localhost:8000/...` and reach the WSL-hosted FastAPI server with no manual port-proxy setup, and a Windows browser can hit `localhost:3000` for the dashboard. Verify this early (Phase 0) rather than assuming it — WSL networking behavior has changed across Windows builds before.
- **Filesystem boundary:** the SQLite file and all app code live on the WSL-native filesystem (ext4), never under `/mnt/c/...` — cross-boundary I/O is slower and, more importantly, `/mnt/c` doesn't reliably fire inotify events, which breaks any filesystem-watcher approach (relevant if Phase 0 lands on Option B). If we do end up polling exported log files written by Windows, poll on an interval rather than relying on a watcher.
- **The one artifact that crosses the boundary:** if Phase 0 lands on Option A (HunterPie plugin), the plugin is a C# DLL that must be loaded by HunterPie.exe on Windows. It can still be *built* from WSL (install the .NET SDK in WSL; the build itself is standard managed C#, no Windows-only APIs needed since HunterPie's plugin API should abstract the memory access) — only the compiled DLL gets copied to `/mnt/c/Users/.../HunterPie/Plugins/` as a deploy step. Everything upstream of that copy (writing the plugin, testing its logic) stays in WSL/normal dev loop; only "does HunterPie load and run it" requires switching to Windows.

**Stack choices and why:**
- **FastAPI** over Node: better fit if the HunterPie plugin ends up dumping JSON files (Python's stdlib + pydantic makes validation trivial), and gives us async WebSocket support if Option A pans out.
- **SQLite for V1**, not Postgres. PRD scope is explicitly single-user/local (Section 7). SQLite removes an entire ops dimension (no server process, no credentials, trivial backup = copy one file) with zero functional loss at this scale. Swapping to Postgres later is a one-line SQLAlchemy connection string change if the schema is designed with that in mind (which it will be — see §4).
- **Next.js + Recharts** over Streamlit: Streamlit is faster to prototype but PRD's FR-3.3 (multi-line real-time overlay) and FR-3.4 (synergy views) benefit from real component control that Streamlit fights you on. If timeline pressure hits, Streamlit is the fallback for Phase 3.

---

## 3. Phased Milestones

### Phase 0 — Ingestion Spike (timebox: 3–5 days, no schema/API work yet)
**Goal:** answer the one open question that determines everything else.
- [ ] Install HunterPie v2 on Windows against current MH Wilds patch; confirm damage meter / monster widget work.
- [ ] **Cross-boundary smoke test (do this before anything else):** on WSL, run `python -m http.server 8000`; from Windows, confirm `curl http://localhost:8000` reaches it. This validates the localhost auto-forwarding the whole architecture depends on, on *this* machine's actual WSL/Windows build, before writing any real code against that assumption.
- [ ] Check HunterPie's plugin documentation/SDK repo for a supported extension point (event hooks, exposed API).
- [ ] If a plugin API exists: scaffold the plugin project in WSL (`dotnet new classlib` + .NET SDK for WSL), write a "hello world" plugin that POSTs one event (e.g., quest start) to a throwaway WSL-hosted endpoint, copy the built DLL to `/mnt/c/Users/.../HunterPie/Plugins/`, and confirm it loads and fires from Windows. Confirm CPU/memory overhead is negligible via Windows Task Manager during a real hunt.
- [ ] If no usable plugin API: locate HunterPie's local export/log file format (check `%appdata%`/install directory for quest logs, damage meter export, or a REST endpoint HunterPie itself might expose for its own web-based widgets). Confirm that path is reachable from WSL either by reading it directly under `/mnt/c` (fine for polling, not for watching) or by having HunterPie push it — polling beats watching here regardless.
- [ ] Deliverable: a short **ADR (architecture decision record)** — "Option A: plugin+WebSocket" or "Option B: log-file polling" — with a fallback plan if HunterPie breaks after a game patch (e.g., staleness alerting, manual re-import).

**Go/no-go gate:** if neither option yields structured per-hunt data (player, weapon, monster, damage, timestamp), stop and reassess — the rest of the PRD depends on this.

### Phase 1 — Data Layer (est. 1 week)
- [ ] Finalize schema (see §4) in SQLite via SQLAlchemy models with Alembic migrations from day one (cheap now, painful to retrofit).
- [ ] Implement FR-2.2 identity resolution: normalize player display names and weapon IDs against a lookup table; handle rename edge cases (flag, don't silently merge).
- [ ] Implement FR-2.3 dedup: unique constraint on `(quest_id, hunt_start_ts)` derived from HunterPie's own quest/session ID if available, else a composite hash of (monster_id, player_ids, start_ts rounded to nearest second).
- [ ] Write a seed/fixture script with fake hunt data so Phases 2–3 aren't blocked on live gameplay.
- [ ] Unit tests for upsert/dedup logic (this is where data corruption bugs hide).

### Phase 2 — Ingestion API (est. 1–1.5 weeks, depends on Phase 0 result)
- [ ] FastAPI service with two ingestion paths per Phase 0 decision:
  - Real-time endpoint (`POST /telemetry/snapshot`) accepting 1–5s interval DPS frames, buffered in-memory per active hunt.
  - Post-hunt endpoint/parser (`POST /telemetry/hunt-complete` or filesystem watcher) that reconciles the buffered snapshots against the final export, resolving any gaps from a dropped connection.
- [ ] Pydantic schema validation per FR-1.3; reject and log (not silently drop) malformed frames.
- [ ] Wrap all multi-table writes in a single DB transaction (FR on data integrity) — a crash mid-hunt must not leave an orphaned `hunt_players` row without a parent `hunts` row.
- [ ] Basic health/status endpoint so the dashboard can show "ingestion online/offline."
- [ ] Load test: simulate 1,000+ historical hunts to validate the <500ms query target from PRD §6 before building the dashboard around unoptimized queries.
- [ ] If Option A: set up a quick deploy loop for the plugin (a small script that builds the DLL in WSL and copies it to the Windows `Plugins/` folder) so iterating on plugin logic doesn't mean manually copying files after every change.

### Phase 3 — Dashboard (est. 1.5–2 weeks) — MVP DONE 2026-09-06 ✅
- [x] FR-3.1 Player Progress Tracker: line chart, rolling DPS + clear time, filterable by monster + weapon.
- [x] FR-3.2 Weapon Performance Matrix: sortable table + bar chart (avg/peak DPS, hunt count, clear rate) by weapon type.
- [x] FR-3.3 Time-Series Damage Curve: multi-line overlay per hunt, all party members, with phase/enrage markers if HunterPie exposes them (stretch — confirm in Phase 0).
- [x] FR-3.4 Teammate Synergy Overview: aggregate table, clear time + contribution % by teammate pairing.
- [x] Loading states and empty states (a new user has zero hunts — dashboard shouldn't look broken).

### Phase 4 — Hardening & Polish (est. 3–5 days)
- [ ] Handle HunterPie version mismatches gracefully: detect and surface "HunterPie version unsupported by our parser" rather than silently ingesting garbage.
- [ ] Crash-recovery test: kill the game mid-hunt, verify no partial/corrupt row lands in the DB (validates the ACID requirement isn't just theoretical).
- [ ] Basic backup/export (copy the SQLite file; document the process).
- [ ] README covering: install steps, HunterPie version compatibility, known limitations (matches PRD's out-of-scope list: no HZV, no auto gear parsing, single-user only).

---

## 4. Schema Sketch (SQLite/Postgres-compatible)

```
players(id, display_name, first_seen_at)
weapons(id, name, weapon_type)              -- weapon_type enum: GS, LS, SnS, DB, ...
monsters(id, name, species)
hunts(id, quest_id_external, monster_id FK, started_at, ended_at, cart_count, cleared BOOLEAN)
hunt_players(hunt_id FK, player_id FK, weapon_id FK, total_damage, peak_dps)
dps_snapshots(id, hunt_id FK, player_id FK, ts_offset_seconds, cumulative_damage, instant_dps)
```

- `hunt_players` is the join table carrying per-hunt-per-player summary stats (feeds FR-3.2, FR-3.4).
- `dps_snapshots` is the raw time-series (feeds FR-3.3); indexed on `(hunt_id, ts_offset_seconds)` for fast curve rendering.
- All FKs indexed; `hunts.started_at` indexed for the rolling-average queries in FR-3.1.

---

## 5. Non-Functional Requirements — how we'll actually verify them

| Requirement | Verification method |
|---|---|
| <1% CPU / <50MB during gameplay | Profile the HunterPie plugin process (Task Manager / dotnet-counters) during a real hunt in Phase 0/2, not just assumed |
| <2s post-hunt persistence | Timestamp log from QuestEnd event to DB commit; add as an automated test in Phase 2 |
| <500ms chart queries at 1,000+ hunts | Load test in Phase 2 with seeded data, before dashboard work starts |
| 0% missing metadata | Treat as a monitored *target*, not a hard gate — log and surface any hunt with missing weapon/monster/player ID rather than pretending it can't happen |

---

## 6. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| HunterPie has no real plugin API for Wilds; only log files | Medium | Phase 0 spike catches this before any other work is sunk |
| HunterPie memory offsets break on each MH Wilds patch | High (per release history) | Post-hunt log fallback (FR-1.2) is not optional — build it even if real-time works, and add a "last known compatible HunterPie version" check |
| Player renames / weapon ID drift break historical continuity (FR-2.2) | Medium | Flag ambiguous matches for manual confirmation rather than auto-merging |
| Solo dev scope creep into V1 (auth, video clips, HZV) | Medium | PRD already scopes these out — hold the line in Phase 4 planning |

---

## 7. Out of Scope (confirmed from PRD, unchanged)
Multi-tenant auth, automated video clip matching, HZV memory extraction, automated gear build parsing.

---

## 8. Rough Timeline
Phase 0: 3–5 days → Phase 1: ~1 week → Phase 2: ~1–1.5 weeks → Phase 3: ~1.5–2 weeks → Phase 4: 3–5 days.
**Total: roughly 5–6 weeks** for a solo developer working part-time, assuming Phase 0 doesn't uncover a dead end.