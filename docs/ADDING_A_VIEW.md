# Adding a view, metric, or tab

Two registries, two one-line additions. Nothing else to touch.

## New metric (backend)

1. Add one function to `backend/app/queries.py` returning JSON-serializable
   dicts. It takes a `Session` plus plain filter params — no FastAPI imports.
   All existing queries handle **n players per hunt** (dicts keyed by
   player id/name, never positional indexing); keep it that way.
2. Expose it with one route in `backend/app/api.py`:

   ```python
   @app.get("/api/my-metric")
   def my_metric(monster_id: int | None = None, db: Session = Depends(get_db)):
       return queries.my_metric(db, monster_id)
   ```

3. Cover it in `backend/tests/test_api.py` (seed via `upsert_hunt`, assert
   through the HTTP route, not the query function directly).
4. Run `./.venv/bin/python -m pytest backend/tests -q`.

## New tab (frontend)

1. Add one component file in `dashboard/components/views/MyView.tsx`
   (`"use client"`, fetch via `apiGet` from `lib/api`, use `seriesColor(i)`
   for per-player series so n-player hunts get distinct colors, render
   `<EmptyState>` when the API returns zero rows). Views receive the hunter
   scope as a `scope: number[]` prop (empty = all hunters) — pass it through
   as `player_ids` to scope-aware endpoints, or dim out-of-scope series.
2. Register it with one entry in `dashboard/lib/registry.tsx`:

   ```tsx
   { id: "mine", title: "Mine", blurb: "What this shows.", render: () => <MyView /> },
   ```

   Tabs, nav, and header update automatically — `app/page.tsx` renders
   everything from `TABS`.

## Conventions

- API base URL: `NEXT_PUBLIC_API_URL`, defaults to `http://localhost:8000`.
- Dark theme tokens live in `dashboard/app/globals.css` (`--bg`, `--accent`, …).
- Per-player chart series: one `<Line dataKey={playerName}>` each, merged onto
  a shared time grid — see `mergeSeries` in `CurveView.tsx`.
- Supporters (`is_supporter`) are excluded from synergy stats server-side;
  don't re-add them in new views without a filter toggle.
