# HunterPie_Analytics

Telemetry & progress analytics for Monster Hunter Wilds via HunterPie v2.

See [PLAN.md](PLAN.md) for the full project plan (architecture, phased milestones, schema sketch).

## Status

Phase 0 closed (GO ✅) — real Wilds hunt imports end-to-end. Dashboard MVP
live with all four Phase 3 views (Progress, Weapons, Damage curves, Synergy).

- Phase 0 work list: [docs/PHASE0_CHECKLIST.md](docs/PHASE0_CHECKLIST.md)
- Ingestion decision record: [docs/ADR-001-ingestion.md](docs/ADR-001-ingestion.md)
- Schema draft (SQLite/Postgres): [db/schema.sql](db/schema.sql)
- Adding views/metrics/tabs: [docs/ADDING_A_VIEW.md](docs/ADDING_A_VIEW.md)

## Backend (Phase 1 — data layer)

```sh
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
.venv/bin/python -m pytest backend/tests -q          # 12 tests
cd backend && ../.venv/bin/python -m app.seed --db hunts.db --hunts 50
```

## Importing real hunts (fork HuntExports JSON)

```sh
cd backend && ../.venv/bin/python -m app.import_hunt --db hunts.db \
  --file "/mnt/c/src/hunt-sample.json"   # or --dir "/mnt/c/.../HuntExports"
```

Maps the fork's quest-end dump (players, per-frame damage, enrage spans)
into the schema; re-imports dedup safely. Monster names resolve from the
Wilds section of HunterPie's `Languages/en-us.xml` (Rise/World share the
numeric ids, so the section matters).

## Dashboard (Phase 3 — Next.js + Recharts)

```sh
cd backend && HUNTS_DB=hunts.db PORT=8000 ../.venv/bin/python -m app.api &  # :8000
cd dashboard && npm install && npm run dev                                   # :3000
```

Open `http://localhost:3000` in the Windows browser (localhost forwards).
API also serves the dashboard queries directly, e.g.
`http://localhost:8000/api/progress`, `/api/weapons`,
`/api/hunts/1/curve`, `/api/synergy`, `/api/filter-options`.
