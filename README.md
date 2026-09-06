# HunterPie_Analytics

Telemetry & progress analytics for Monster Hunter Wilds via HunterPie v2.

See [PLAN.md](PLAN.md) for the full project plan (architecture, phased milestones, schema sketch).

## Status

Phase 0 — Ingestion spike (go/no-go on HunterPie data source). Nothing else starts until Phase 0 concludes.

- Phase 0 work list: [docs/PHASE0_CHECKLIST.md](docs/PHASE0_CHECKLIST.md)
- Ingestion decision record: [docs/ADR-001-ingestion.md](docs/ADR-001-ingestion.md)
- Schema draft (SQLite/Postgres): [db/schema.sql](db/schema.sql)

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
