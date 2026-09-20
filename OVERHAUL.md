# Overhaul v2 — Tracking Doc

Base: `main` @ `f6c4780` (party-size filter). Branch: `overhaul/v2`.
Phased PRs: `overhaul/v2-phase-{0..6}` → squash into `overhaul/v2` → final PR to `main`, tag `v2.0`.

Constraint: **migrate existing `hunts.db`, no fresh DB, no silent data loss.**
Stack stays (FastAPI + SQLite + Next.js/Recharts); swaps allowed where justified.
Out of scope: live feed/WebSocket (ADR-001), multi-tenant auth, video clips, HZV.

## Baseline (2026-09-20, pre-overhaul)

| Metric | Value |
|---|---|
| `backend/app/queries.py` | 1482 lines (god-module) |
| `backend/app/api.py` | 263 lines |
| Backend tests | 47 passed (`pytest tests -q`) |
| Dashboard `tsc --noEmit` | clean |
| Dashboard tabs | 12 views in `components/views/` |
| README tabs table | stale (lists 8, registry has 12) |

## Phases

- [ ] **Phase 0 — Baseline & setup.** Record perf bench (200-hunt seed: time `/api/quests`, `/api/synergy`, `/api/compare`, `/api/high-scores`); screenshot all 12 tabs. ✅ (this doc; bench + screenshots pending)
- [ ] **Phase 1 — Backend foundation.** Single Engine + per-connection pragmas (`WAL`/`busy_timeout`/`foreign_keys=ON`); Alembic (drop `EXTRA_COLUMNS`; add missing `player_abnormalities` table, hot-filter indexes, CHECK constraints, `dedup_hash NOT NULL` backfill); split `queries.py` (`filters.py`, `engagement.py`, `variants.py`, `metrics/`); SQL-side aggregation; Pydantic query validation + keyset pagination; identity hardening (`player_aliases`, canonical names); `import_job` single-flight + LRU + cancel; multi-monster `quest_damage`/`attributed_damage` + sibling lookup by `quest_id_external`.
- [ ] **Phase 2 — Frontend data layer + design system.** TanStack Query hooks + URL searchParams state; one `FilterBar`; `ScopeProvider`; theme-aware chart kit (`mergeSeries` in `lib/metrics`, ~500pt downsample); one `Modal`; tokens + `cva` primitives; virtualized lists; `SearchSelect` v2 (`cmdk`); OpenAPI→zod types; `noUnused`.
- [ ] **Phase 3 — Performance budget.** Async routes + `run_in_threadpool`; `Cache-Control/ETag` on `filter-options`/`activity`; p95 targets at 1000 hunts: `/progress` <200ms, `/quests` <300ms, `/synergy` <400ms. CI bench.
- [ ] **Phase 4 — UX polish + 2–3 new features.** Unify empty/loading/error; toasts + retry; mobile header fix; `DEFAULT_PARTY_SIZE` → `All` default. Candidates: build optimizer, curve timeline scrubber, pairing recommender, shareable hunt link, HunterPie staleness banner.
- [ ] **Phase 5 — Tests & tooling.** `test_ingest`/`test_import_job`/`test_schema_drift`/200-hunt perf test (target 60+ tests); Vitest + Playwright visual diff; Ruff + mypy strict; `docker-compose.yml`; `Makefile`; GitHub Actions; pre-commit.
- [ ] **Phase 6 — Migration & cutover.** `alembic upgrade head` dry-run on prod DB copy + row-count diff; PR to `main`, tag `v2.0`; README refresh; delete stale branches (`tmp-pr`, `feat/high-scores` remnants).

## Decision log

| Date | Decision |
|---|---|
| 2026-09-20 | Branch `overhaul/v2` cut from `main` @ `f6c4780`; phased-PR strategy. |
| 2026-09-20 | Priorities: code health + performance + UX polish + new features; migrate (don't break) `hunts.db`. |

## Left untracked (deliberately NOT committed to main)

`.playwright-mcp/`, `backend/hunts.db-shm`, `backend/hunts.db-wal` (SQLite runtime artifacts — consider adding `*.db-shm`/`*.db-wal` to `.gitignore`), root `curves-*.png` + `final-dashboard.png` (screenshots — move under `docs/` or ignore if not needed).
