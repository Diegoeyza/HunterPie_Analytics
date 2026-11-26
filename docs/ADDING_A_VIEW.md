# Adding a view, metric, or tab

Two registries, two one-line additions. Nothing else to touch.

## New metric (backend)

1. Add one function to `backend/app/queries.py` returning JSON-serializable
   dicts. It takes a `Session` plus plain filter params — no FastAPI imports.
   All existing queries handle **n players per hunt** (dicts keyed by
   player id/name, never positional indexing); keep it that way.
   Funnel hunt selection through `backend/app/filters.py`
   (`filters.visible()`, `filters.party(stmt, n)`) so scope/party/visibility
   semantics match every other tab. Shared logic lives in
   `engagement.py` (DPS windows) and `variants.py` (gear fingerprints).
2. Expose it with one validated route in `backend/app/api.py`:

   ```python
   @app.get("/api/my-metric")
   def my_metric(monster_id: int | None = None,
                 players: int | None = None,
                 db: Session = Depends(get_db)):
       return queries.my_metric(db, monster_id, party=_party(players))
   ```

   Bounds via `Query(ge/le)`, id lists via `_ids()` (422 on garbage),
   PATCH bodies as Pydantic models (never `body: dict`).
3. Cover it in `backend/tests/test_api.py` (seed via `upsert_hunt`, assert
   through the HTTP route, not the query function directly). New tables or
   columns must also be added to `db/schema.sql` — `test_schema_drift`
   fails the build on models/schema drift.
4. Run `make test` (pytest + dashboard typecheck) and
   `.venv/bin/python -m ruff check backend/app backend/tests`.

## New tab (frontend)

1. Add one component file in `dashboard/components/views/MyView.tsx`
   (`"use client"`). Data via `useApi<T>(path, params)` from `lib/useApi`
   (cached, stable keys, `null` params skips — no hand-rolled
   useEffect fetches). Filters via `components/FilterBar.tsx`
   (`MonsterSelect`/`StarsSelect`/`WeaponSelect`/`HunterSelect`,
   `useQuestOptions`); charts via `components/ChartKit.tsx`
   (`GRID_STROKE`, `TICK`, `ChartTip` — theme-aware, never hardcoded
   hex). Numbers via `lib/format.ts` (`fmtDps`/`fmtTime`/`fmtPct`/`fmtInt`).
   Use `seriesColor(i)` for per-player series so n-player hunts get
   distinct colors; render `<EmptyState>` / `<ScopeEmpty>` on zero rows
   and `<ApiState error loading>` while fetching.
   Views receive the hunter scope as a `scope: number[]` prop (empty = all
   hunters) — pass it as `player_ids` to scope-aware endpoints, or dim
   out-of-scope series. Global state (tab/scope/party) syncs to the URL
   automatically via `lib/url.ts` — no per-view work needed.
2. Register it with one entry in `dashboard/lib/registry.tsx` (`title`/`blurb`
   are translation keys, not text):

   ```tsx
   { id: "mine", title: "tab.mine", blurb: "tab.mine.blurb", render: () => <MyView /> },
   ```

   `app/page.tsx` renders everything from `TABS`, so tabs, nav, blurbs and
   `<html lang>` update automatically.

## Translations (en + ja)

Every user-facing string lives in `dashboard/locales/<locale>/`, one JSON file
per screen area (`common`, `table`, `views.mine`, …), composed by
`locales/<locale>/index.ts`. There are no keys in code paths other than `t()`.

1. `const { t } = useT();` from `@/lib/i18n` — `t("mine.title", { n })`
   interpolates `{n}`. In non-component helpers call the exported plain `t`
   (it reads the active locale).
2. Add the key to `locales/en/views.mine.json` **and**
   `locales/ja/views.mine.json` (or add a new area: one JSON pair + one import
   + one spread in both index files).
3. Plurals: two keys chosen in code (`"mine.hunts.one"` / `"mine.hunts.other"`);
   Japanese uses the same wording for both.
4. Data names never go in the dictionary — use `lib/names.ts`:
   `monsterName(name, monster_id)`, `abnormalityName(id, name)`,
   `awardName(id, name)`, `weaponTypeName(type)`. They fall back to the stored
   English name, so payloads must carry the id (see `queries.py`).
5. Numbers/dates: `lib/format.ts` (`fmtInt`, `fmtDate`, …) already use the
   active locale — never hand-build `toLocaleString()` strings. Decimals and
   percentages (`fmtDps`, `fmtPct`) are locale-neutral by design.
6. Verify: `npm run check:i18n` (key parity + `{placeholder}` drift, runs in
   CI) and `npx tsc --noEmit`. Visual check: `python scripts/check_ja_ui.py
   --base <url>` sweeps every tab in Japanese for leftover English.
7. Reviewer hand-off: `npm run i18n:sheet` regenerates
   `docs/i18n/japanese-review.md` + `.csv`; terminology rules are in
   `docs/i18n-glossary-ja.md`.

## Conventions

- API base URL: `NEXT_PUBLIC_API_URL`, defaults to `http://localhost:8000`.
- Theme tokens live in `dashboard/app/globals.css` (`--bg`, `--accent`,
  `--chart-grid`, `--chart-tick`, …); charts must resolve colors through
  them so light mode stays readable.
- Per-player chart series: one `<Line dataKey={playerName}>` each, merged onto
  a shared time grid — see `mergeSeries` in `CurveView.tsx`.
- Supporters (`is_supporter`) are excluded from synergy stats server-side;
  don't re-add them in new views without a filter toggle.
- Modals: use `components/Modal.tsx` (portal + Escape + scroll-lock).
  Notifications: `useToast()` from `components/Toast.tsx`. Mutations must
  call `apiInvalidate()` instead of reloading the page.
- Migrations: never hand-edit a prod DB. Add columns/indexes to models +
  `db/schema.sql` and a versioned step in `app/db.py:MIGRATIONS`
  (idempotent, guarded by `PRAGMA user_version`).
