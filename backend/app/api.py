"""FastAPI dashboard API + import hook.

Run:  cd backend && ../.venv/bin/python -m app.api   (serves :8000)
DB:   $HUNTS_DB or backend/hunts.db. Port: $PORT or 8000.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import queries
from .db import DEFAULT_DB_PATH, make_session
from .import_hunt import (
    DEFAULT_EXPORTS_DIR,
    DEFAULT_GAME_VERSION,
    DEFAULT_HUNTERPIE_VERSION,
    import_doc,
    load_monster_names,
)

DB_PATH = Path(os.environ.get("HUNTS_DB", DEFAULT_DB_PATH))

app = FastAPI(title="HunterPie Analytics")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    session = make_session(DB_PATH)
    try:
        yield session
    finally:
        session.close()


@app.get("/api/filter-options")
def filter_options(db: Session = Depends(get_db)):
    return queries.filter_options(db)


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    return queries.health(db)


@app.get("/api/hunts")
def hunts(limit: int = 200, include_ignored: bool = False,
          db: Session = Depends(get_db)):
    return queries.hunt_list(db, limit, include_ignored)


@app.get("/api/progress")
def progress(monster_id: int | None = None, weapon_id: int | None = None,
             player_id: int | None = None, quest_id: int | None = None,
             stars: int | None = None, player_ids: str | None = None,
             window: int = 5, variant_id: int | None = None,
             db: Session = Depends(get_db)):
    return queries.progress(db, monster_id, weapon_id, player_id,
                            quest_id, stars, queries._parse_ids(player_ids),
                            window, variant_id)


@app.get("/api/progress/improvement")
def progress_improvement(player_id: int | None = None, top_n: int = 5,
                         weapon_id: int | None = None,
                         player_ids: str | None = None,
                         monster_id: int | None = None,
                         stars: int | None = None,
                         variant_id: int | None = None,
                         db: Session = Depends(get_db)):
    return queries.progress_improvement(db, player_id, top_n, weapon_id,
                                        queries._parse_ids(player_ids),
                                        monster_id, stars, variant_id)



@app.get("/api/weapons")
def weapons(player_ids: str | None = None, monster_id: int | None = None,
            stars: int | None = None, variant_id: int | None = None,
            db: Session = Depends(get_db)):
    return queries.weapon_matrix(db, queries._parse_ids(player_ids), monster_id,
                                 stars, variant_id)


@app.get("/api/hunts/{hunt_id}/curve")
def curve(hunt_id: int, max_points: int = 500, quest_hp: bool = False,
          db: Session = Depends(get_db)):
    try:
        return queries.hunt_curve(db, hunt_id, max_points, quest_hp)
    except KeyError:
        raise HTTPException(404, f"hunt {hunt_id} not found")


@app.get("/api/hunts/{hunt_id}/abnormalities")
def abnormalities(hunt_id: int, db: Session = Depends(get_db)):
    try:
        return queries.hunt_abnormalities(db, hunt_id)
    except KeyError:
        raise HTTPException(404, f"hunt {hunt_id} not found")


@app.get("/api/synergy")
def synergy(player_ids: str | None = None, monster_id: int | None = None,
            stars: int | None = None, variant_id: int | None = None,
            db: Session = Depends(get_db)):
    return queries.synergy(db, queries._parse_ids(player_ids), monster_id,
                           stars, variant_id)


@app.get("/api/quests")
def quests(db: Session = Depends(get_db)):
    return queries.quest_stats(db)


@app.get("/api/records")
def records(db: Session = Depends(get_db)):
    return queries.records(db)


@app.get("/api/high-scores")
def high_scores(player_ids: str | None = None, monster_id: int | None = None,
                weapon_id: int | None = None, stars: int | None = None,
                sort_by: str = "dps", limit: int | None = None,
                variant_id: int | None = None,
                include_ignored: bool = False, db: Session = Depends(get_db)):
    return queries.high_scores(db, queries._parse_ids(player_ids), monster_id,
                               weapon_id, stars, sort_by, limit, variant_id,
                               include_ignored)


@app.patch("/api/hunts/{hunt_id}/ignore")
def ignore_hunt(hunt_id: int, body: dict, db: Session = Depends(get_db)):
    """Hide (ignored=true) or restore a hunt from every stat view."""
    try:
        return queries.set_hunt_ignored(db, hunt_id, bool(body.get("ignored", True)))
    except KeyError:
        raise HTTPException(404, f"hunt {hunt_id} not found")


@app.get("/api/activity")
def activity(db: Session = Depends(get_db)):
    return queries.activity(db)


@app.get("/api/compare")
def compare(player_ids: str | None = None, window: int = 5,
            variant_id: int | None = None, db: Session = Depends(get_db)):
    return queries.compare(db, queries._parse_ids(player_ids), window,
                           variant_id)


@app.get("/api/players/{player_id}/variants")
def player_variants(player_id: int, db: Session = Depends(get_db)):
    return queries.player_variants(db, player_id)


@app.patch("/api/weapon-identities/{identity_id}")
def rename_identity(identity_id: int, body: dict,
                    db: Session = Depends(get_db)):
    try:
        return queries.set_identity_label(db, identity_id, body.get("label"))
    except KeyError:
        raise HTTPException(404, f"weapon identity {identity_id} not found")


@app.post("/api/import")
def import_hunts(db: Session = Depends(get_db)):
    """Import HuntExports JSON dumps (dedup-safe: re-imports skip).

    Source dir: $HUNT_EXPORTS or the HunterPie default. Powers the
    dashboard Import button so hunts can be pulled without the CLI.
    """
    import json

    src = Path(os.environ.get("HUNT_EXPORTS", str(DEFAULT_EXPORTS_DIR)))
    if not src.is_dir():
        raise HTTPException(404, f"hunt exports dir not found: {src}")
    names = load_monster_names(None)
    imported_ids: list[int] = []
    duplicates = 0
    errors: list[dict] = []
    for path in sorted(src.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as e:
            errors.append({"file": path.name, "error": str(e)})
            continue
        try:
            for hunt, created, _warnings in import_doc(
                    db, doc, names,
                    DEFAULT_HUNTERPIE_VERSION, DEFAULT_GAME_VERSION):
                if created:
                    imported_ids.append(hunt.id)
                else:
                    duplicates += 1
        except (ValueError, KeyError) as e:
            db.rollback()
            errors.append({"file": path.name, "error": str(e)})
    return {"scanned": len(list(src.glob('*.json'))),
            "imported": len(imported_ids),
            "imported_ids": imported_ids,
            "duplicates": duplicates,
            "errors": errors}


@app.get("/api/players/pins")
def pins(db: Session = Depends(get_db)):
    return queries.list_pins(db)


@app.post("/api/players/{player_id}/pin")
def pin(player_id: int, db: Session = Depends(get_db)):
    try:
        return queries.set_pin(db, player_id, True)
    except KeyError:
        raise HTTPException(404, f"player {player_id} not found")


@app.delete("/api/players/{player_id}/pin")
def unpin(player_id: int, db: Session = Depends(get_db)):
    try:
        return queries.set_pin(db, player_id, False)
    except KeyError:
        raise HTTPException(404, f"player {player_id} not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api:app", host="127.0.0.1",
                port=int(os.environ.get("PORT", 8000)))
