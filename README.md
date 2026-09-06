# HunterPie Analytics

Post-hunt dashboard for **Monster Hunter Wilds** via [HunterPie v2](https://github.com/HunterPie/HunterPie).

Imports per-hunt JSON dumps (quest-end snapshots) into SQLite and visualises them
with Next.js + Recharts.

## How it works

```
HunterPie (analytics-export fork)
  → quest-end JSON dumped to HuntExports/
    → import_hunt.py parses + upserts into SQLite
      → FastAPI serves /api/* endpoints
        → Next.js dashboard fetches and renders
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- [HunterPie](https://github.com/HunterPie/HunterPie) with the [analytics-export fork](https://github.com/Diegoeyza/HunterPie) for real data

## Quick start

```sh
# 1. Set up
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm install --prefix dashboard

# 2. Seed demo data (31 synthetic hunts)
cd backend && ../.venv/bin/python -m app.seed --db hunts.db --hunts 31 && cd ..

# 3. Run
./start.sh   # API → :8000, Dashboard → :3000
```

Open **http://localhost:3000**.

## Importing real hunts

With the [analytics-export fork](https://github.com/Diegoeyza/HunterPie) installed,
every quest completion dumps a JSON to `C:\Program Files\HunterPie\HuntExports\`.

```sh
# Import all hunts from HuntExports
./import.sh

# Single file
./import.sh --file "/mnt/c/src/hunt-sample.json"

# Custom folder
./import.sh --dir "/path/to/HuntExports"
```

Re-imports are idempotent — existing hunts are skipped, new ones are added.
Run `./import.sh` after each hunting session to pull in new data.

## Scripts

| Script | What it does |
|--------|-------------|
| `./start.sh` | Starts API (`:8000`) + dashboard (`:3000`). Ctrl+C kills both. |
| `./import.sh` | Imports hunt JSONs from `C:\Program Files\HunterPie\HuntExports\`. |
| `./import.sh --file path.json` | Imports a single hunt file. |
| `./import.sh --dir /path` | Imports from a custom directory. |

## Dashboard

### Tabs

| Tab | What it shows |
|-----|---------------|
| **Progress** | DPS per hunt + rolling average, clear time trend. Filters: monster, quest, stars, weapon, hunter. |
| **Weapons** | Average DPS, peak hit*, hunt count, clear rate by weapon type. |
| **Damage curves** | Per-hunt cumulative damage or DPS (5s rolling avg) for all party members, monster HP overlay, enrage shading. |
| **Quests** | Per-quest aggregates: clear rate, best DPS, enrage uptime. |
| **Records** | Personal bests per monster: fastest clear, highest DPS. |
| **Compare** | Scoped hunters vs whole-party DPS, hunt by hunt. |
| **Activity** | Hunts per day, clear rate, total damage. |
| **Synergy** | Clear time and damage share by teammate pairing. |

\* *Peak hit = largest single damage frame (~1s sampling), not sustained DPS.*

### Scope bar

Star hunters in the top bar to focus views on specific players.
Scope applies to Progress, Weapons, Damage curves, Compare, and Synergy.
Stored in `localStorage` — survives refreshes.

### Damage curves features

- **Metric toggle**: Cumulative damage or DPS (5s rolling average)
- **Monster HP overlay**: Dashed red line, right Y-axis (0–100%)
- **Enrage markers**: Light red shaded regions on the chart
- **DPS from first hit**: Calculated from each player's first attack, not quest start
- **Multi-party**: All party members plotted on the same grid

## Architecture

### Backend (`backend/`)

- **Framework**: FastAPI + SQLAlchemy + SQLite
- **Tables**: `players`, `weapons`, `monsters`, `hunts`, `hunt_players`, `dps_snapshots`, `monster_events`, `monster_health_steps`, `player_pins`
- **API port**: `:8000` (or `$PORT`)
- **DB path**: `backend/hunts.db` (or `$HUNTS_DB`)
- **Schema**: `db/schema.sql`
- **Migration**: Pre-Alembic — `init_db()` runs `ALTER TABLE` for new columns on existing DBs

### Dashboard (`dashboard/`)

- **Framework**: Next.js 15 + Recharts 3 + TypeScript
- **Port**: `:3000`
- **API URL**: `http://localhost:8000` (or `$NEXT_PUBLIC_API_URL`)
- **Pattern**: Tab registry — add a view by creating a file in `components/views/` and adding an entry to `lib/registry.tsx`

### Key files

```
backend/
  app/api.py            FastAPI routes + CORS
  app/queries.py        All metric queries (one function per tab)
  app/ingest.py         upsert_hunt() — atomic, idempotent, n-player
  app/import_hunt.py    Poogie JSON parser + CLI
  app/seed.py           Deterministic demo data generator
  app/db.py             init_db() with pre-Alembic migration
  app/models.py         SQLAlchemy models (9 tables)
  tests/                19 tests (import + API)

dashboard/
  app/page.tsx          Root page, scope state, tab rendering
  lib/registry.tsx      Tab registry (TABS array)
  lib/api.ts            Typed fetch helpers
  components/views/     One file per tab
  components/ScopeBar.tsx   Hunter pin/scope UI

db/schema.sql           Source of truth for schema
docs/ADDING_A_VIEW.md   How to add new tabs/metrics
```

## Adding a new tab

1. Create `dashboard/components/views/MyView.tsx`
2. Add entry to `dashboard/lib/registry.tsx`:
   ```ts
   { id: "my-tab", title: "My Tab", blurb: "Description.", render: (ctx) => <MyView scope={ctx.scope} /> }
   ```
3. Add query to `backend/app/queries.py`
4. Add route to `backend/app/api.py`
5. Done — no other files change.

See [docs/ADDING_A_VIEW.md](docs/ADDING_A_VIEW.md) for details.

## Adding a new metric to an existing tab

1. Add query function in `backend/app/queries.py`
2. Add route in `backend/app/api.py`
3. Fetch it in the view component

## Tests

```sh
# Backend (19 tests)
cd backend && ../.venv/bin/python -m pytest tests -q

# Dashboard (type check)
cd dashboard && npx tsc --noEmit
```

## Known limitations

- **Abnormality/buff uptime**: Counted by HunterPie but not stored yet (8 tracks per player reported as warnings on import)
- **Multi-monster quests**: Only `monsters[0]` is imported (others reported as warnings)
- **HunterPie/game versions**: Not in the JSON dump — defaults to `2.14.0.466` / `1.042.00.02`, override with `--hunterpie-version` / `--game-version`

## License

Private — [Diegoeyza](https://github.com/Diegoeyza)
