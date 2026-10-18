# Sharing this project

The kit is three independent pieces. Hand over the whole thing, or just the
piece the recipient needs — the **REFramework mod** is a single Lua file and the
easiest to share on its own.

```
REFramework mod ─┐
                 ├─→ HuntExports/*.json ─→ import_hunt.py ─→ SQLite ─→ FastAPI ─→ dashboard
HunterPie fork ──┘
```

Both sources feed the same importer. A hunt captured by both is merged, never
double-counted. HunterPie owns damage, weapon classes and DPS curves; the mod
adds the 30 quest awards (hunter highlights), the local player's weapon name,
and CPU-supporter flags.

---

## 1. REFramework mod — `hunt_dumper.lua`

The in-game mod. At quest end it writes a JSON dump the dashboard imports.

**Install**

1. Install [REFramework](https://github.com/praydog/REFramework) for MH Wilds
   (`dinput8.dll` in the game folder) if not already present.
2. Copy `hunt_dumper.lua` to:

   ```
   <game>\reframework\autorun\hunt_dumper.lua
   ```

   Steam path:
   `...\steamapps\common\MonsterHunterWilds\reframework\autorun\`
3. In-game, open the REFramework menu → **HuntDumper** to confirm it is enabled.
4. Dumps appear at quest end in `<game>\reframework\data\HuntExports\*.json`.

**Notes**

- Load the script **before** a quest starts. Reloading scripts mid-hunt resets
  its state, so that hunt is skipped (the next one is fine).
- Captures: quest metadata, monster id + HP curve, per-player damage totals,
  the 30 quest awards, CPU-supporter flags, and the local player's weapon name.
- It does **not** capture per-player weapon classes or DPS curves — HunterPie
  (piece 2) owns those.
- The local weapon *name* is still being calibrated (it can resolve the wrong
  model). Damage totals and awards are unaffected.

---

## 2. HunterPie analytics-export fork (for damage + DPS curves)

Upstream HunterPie v2 does not expose hunt exports locally, so this project uses
a small fork that dumps each quest to JSON.

- Fork: <https://github.com/Diegoeyza/HunterPie> — branch `analytics-export`,
  Apache-2.0. Building it needs the .NET 10 Windows SDK; output lands in
  `HuntExports/`.
- If you're not shipping a prebuilt binary with this bundle, the recipient can
  build it, or run with the REFramework mod only (awards + HP curves, no
  per-player DPS curves).

---

## 3. Analytics app (this repo)

FastAPI + SQLite backend and a Next.js dashboard, packaged as a Windows
desktop app (native window via WebView2) with a static UI served by the backend.

**For friends / players (recommended)**

Grab `HunterPieAnalytics-Setup-<version>.exe` from the releases page and run it
(per-user install, no admin). Or install from the Microsoft Store. The app runs
entirely offline — see [PRIVACY.md](../PRIVACY.md).

The direct-download installer/exe is **not code signed yet** (Windows may warn;
see [code signing notes](../docs/CODE_SIGNING.md)). The Microsoft Store build
is re-signed by Microsoft.

**Docker (cross-platform dev / server)**

```sh
HUNT_EXPORTS="/path/to/HuntExports" docker compose up --build
# dashboard → http://localhost:3000
```

`HUNT_EXPORTS` may point at the HunterPie `HuntExports/` folder **or** the mod's
`reframework/data/HuntExports/`. It defaults to `./seeds` (demo data).

**From source**

```sh
make setup        # venv + pip + npm
make seed         # optional demo data
make dev          # API :8000 + dashboard :3000
./import.sh       # import new dumps (idempotent — safe to re-run)
```

See `README.md` for the full command list and architecture.

---

## Building a shareable bundle

```sh
make package      # or: ./package.sh
```

Writes to `dist/`:

| File | Contents |
|------|----------|
| `hunt-dumper-<version>.zip` | The REFramework mod + `INSTALL.txt` (drop-in). |
| `HunterPie-Analytics-src-<sha>.zip` | Full app source, git-tracked files only — no venv, `node_modules`, or DB. |

Tagged releases (`v*`) are built entirely by CI
(`.github/workflows/release.yml`) and attach all end-user artifacts:

| File | Contents |
|------|----------|
| `HunterPieAnalytics-Setup-<ver>.exe` | One-click per-user installer: desktop app + bundled Lua mod + companion. |
| `HuntDumper-<ver>.zip` | REFramework mod in game-folder layout (Vortex/Nexus). |
| `SHA256SUMS.txt` | Checksums for the two artifacts above. |

(The MSIX/Store package and a standalone companion zip are no longer attached
to releases; build the MSIX locally with `packaging/msix/build-msix.ps1` if
needed, and the companion ships inside the installer.)

For publishing the mod on Nexus Mods, see [NEXUS.md](NEXUS.md).
