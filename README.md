# HunterPie Analytics

Post-hunt dashboard for Monster Hunter Wilds via [HunterPie v2](https://github.com/HunterPie/HunterPie).

Imports per-hunt JSON dumps (quest-end snapshots) into SQLite and visualises them
with Next.js + Recharts.

## Prerequisites

- Python 3.10+
- Node.js 18+
- (Optional) HunterPie with the [analytics-export fork](https://github.com/Diegoeyza/HunterPie) for real data

## Quick start (seeded demo)

```sh
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
cd backend && ../.venv/bin/python -m app.seed --db hunts.db --hunts 31 && cd ..
./start.sh   # API → :8000, Dashboard → :3000
```

Open `http://localhost:3000`. 31 synthetic hunts across 4 monsters, 5 weapons, 5 hunters.

## Importing real hunts

With the [analytics-export fork](https://github.com/Diegoeyza/HunterPie) installed,
hunt JSONs are dumped to `Documents/HunterPie/HuntExports/` on quest end.

```sh
# Auto-detects HuntExports at /mnt/c/Users/diego/Documents/HunterPie/HuntExports
./import.sh

# Or point to a specific folder
./import.sh --dir "/mnt/c/Users/diego/Documents/HunterPie/HuntExports"

# Single file
./import.sh --file "/mnt/c/src/hunt-sample.json"
```

## Running

```sh
./start.sh              # starts both API (:8000) and dashboard (:3000)
./import.sh             # import real hunts from HuntExports
```

Both must run simultaneously. The dashboard fetches from the API.

## Dashboard tabs

| Tab | What it shows |
|-----|---------------|
| **Progress** | DPS per hunt + rolling average, clear time trend. Filters: monster, quest, stars, weapon, hunter. |
| **Weapons** | Average DPS, peak hit, hunt count, clear rate by weapon type. |
| **Damage curves** | Per-hunt cumulative damage or DPS (5s rolling) for all party members, monster HP overlay, enrage shading. |
| **Quests** | Per-quest aggregates: clear rate, best DPS, enrage uptime. |
| **Records** | Personal bests per monster: fastest clear, highest DPS. |
| **Compare** | Scoped hunters vs whole-party DPS, hunt by hunt. |
| **Activity** | Hunts per day, clear rate, total damage. |
| **Synergy** | Clear time and damage share by teammate pairing. |

## Scope bar

Star hunters in the top bar to focus views on specific players.
Scope applies to Progress, Weapons, Damage curves, Compare, and Synergy.
Stored in localStorage — survives refreshes.

## Architecture

```
HunterPie plugin (fork)
  → quest-end JSON dump to HuntExports/
    → import_hunt.py parses + upserts into SQLite
      → FastAPI serves /api/* endpoints
        → Next.js dashboard fetches and renders
```

- **Backend**: FastAPI + SQLAlchemy + SQLite. 9 tables, ~450 lines of queries.
- **Dashboard**: Next.js 15 + Recharts 3 + TypeScript. Tab registry pattern — add a view by dropping a file in `components/views/` and registering it in `lib/registry.tsx`.
- **Schema**: see `db/schema.sql`. Pre-Alembic migration handles column additions on existing DBs.

## Tests

```sh
cd backend && ../.venv/bin/python -m pytest tests -q    # 19 tests
cd dashboard && npx tsc --noEmit                         # type check
```

## Adding a view

See [docs/ADDING_A_VIEW.md](docs/ADDING_A_VIEW.md). One component file + one registry entry.
