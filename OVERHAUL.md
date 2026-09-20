# Overhaul v2 — Tracking Doc

Base: `main` @ `f6c4780` (party-size filter). Branch: `overhaul/v2`.
Phased PRs: `overhaul/v2-phase-{0..6}` → squash into `overhaul/v2` → final PR to `main`, tag `v2.0`.

Constraint: **migrate existing `hunts.db`, no fresh DB, no silent data loss.**
Stack stays (FastAPI + SQLite + Next.js/Recharts); swaps allowed where justified.
Out of scope: live feed/WebSocket (ADR-001), multi-tenant auth, video clips, HZV.

## Baseline (2026-09-20, pre-overhaul)

| Metric | Before | After |
|---|---|---|
| `backend/app/queries.py` | 1482 lines (god-module) | 1190 lines + `filters.py`/`engagement.py`/`variants.py` |
| Backend tests | 47 passed | 71 passed |
| Dashboard `tsc --noEmit` | clean | clean |
| Dashboard tabs | 12 views | 13 views (+ Review) |
| 1000-hunt bench p-best | progress 164ms, high-scores 105ms, improvement 101ms | progress 154ms, high-scores 96ms, improvement 92ms (no regressions) |

Bench verdict: everything already <500ms at 1000 hunts — Phase 3 became
hold-the-line (bench.py committed for CI) instead of emergency surgery.

## Phases

- [x] **Phase 0 — Baseline & setup.** ✅ (bench + screenshots pending → bench done)
- [x] **Phase 1 — Backend foundation.** Single Engine + per-connection pragmas; versioned migrations (user_version, v1+v2); queries split; SQL pushdowns; Pydantic validation + 422/409; ingest validation + aliases + external-first dedup + split flags; import_job single-flight/cancel/warnings; seed refresh.
- [x] **Phase 2 — Frontend data layer + design system.** `useApi` hook (12/13 views; ScopeBar uses `useFilterOptions`), URL state (tab/scope/party), one `FilterBar`, theme-aware `ChartKit`, one `Modal`, toasts (no reloads), `SearchSelect` clear + Enter fix, `fmt*` unification (fmtDmg removed), `ScopeBar.storeScope` dedupe, Buffs honors scope, health versions tooltip.
- [x] **Phase 3 — Performance budget.** Bench before/after (no regressions, small gains). HuntsManager still full-renders ≤2000 rows — virtualization deferred (only reached via header manager; main Hunts tab is server-limited to 500).
- [x] **Phase 4 — UX polish + new features.** Review tab (alias merge/dismiss) + backend endpoints; import cancel button + 409 handling + warnings toast; consistent ApiState loading/error; mobile CSS untouched (deferred — header still crowds at 390px).
- [x] **Phase 5 — Tests & tooling.** 71 tests (+drift/validation/job/ingest/alias suites); ruff clean; `Makefile`; GitHub Actions (pytest + tsc); `Dockerfile` + `docker-compose.yml`; `.gitignore` (db-shm/wal, playwright-mcp); `bench.py`; `docs/ADDING_A_VIEW.md` refresh.
- [ ] **Phase 6 — Migration & cutover.** ✅ dry-run on prod copy (307 hunts, v0→v2, zero row drift). Remaining: merge to `overhaul/v2` → PR to `main`, tag `v2.0`; delete stale branches.

## Decision log

| Date | Decision |
|---|---|
| 2026-09-20 | Branch `overhaul/v2` cut from `main` @ `f6c4780`; phased-PR strategy. |
| 2026-09-20 | Priorities: code health + performance + UX polish + new features; migrate (don't break) `hunts.db`. |
| 2026-09-20 | Versioned `user_version` migrations in `db.py` instead of Alembic (single-user SQLite; zero new deps; covered by `test_schema_drift` + prod-copy dry-run). `EXTRA_COLUMNS` kept as v1 content. |
| 2026-09-20 | `players.canonical` is a NON-unique lookup aid: existing contract (test) demands case-variant rows coexist ("flag, never merge"); UNIQUE would force silent merges. |
| 2026-09-20 | SWR-lite `useApi` instead of TanStack Query (no new dep; 60s cache + invalidate covers tab-switch churn at this scale). |
| 2026-09-20 | `DEFAULT_PARTY_SIZE = 4` kept (user's shipped feature; All is one click away). |
| 2026-09-20 | Quests/Activity stay scope-global (quest/day aggregates); documented in README. Buffs now honors scope. |
| 2026-09-20 | Deferred: keyset pagination (limit bounds suffice at ≤2000 rows), list virtualization, cmdk combobox, mobile header rework, `dedup_hash NOT NULL` backfill (nullable tolerated; external-id match is primary). |

## Left untracked (deliberately NOT committed to main)

`.playwright-mcp/`, `backend/hunts.db-shm`, `backend/hunts.db-wal` (SQLite runtime artifacts — consider adding `*.db-shm`/`*.db-wal` to `.gitignore`), root `curves-*.png` + `final-dashboard.png` (screenshots — move under `docs/` or ignore if not needed).
