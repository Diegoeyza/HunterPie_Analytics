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
def hunts(limit: int = 200, db: Session = Depends(get_db)):
    return queries.hunt_list(db, limit)


@app.get("/api/progress")
def progress(monster_id: int | None = None, weapon_id: int | None = None,
             player_id: int | None = None, quest_id: int | None = None,
             stars: int | None = None, player_ids: str | None = None,
             window: int = 5, db: Session = Depends(get_db)):
    return queries.progress(db, monster_id, weapon_id, player_id,
                            quest_id, stars, queries._parse_ids(player_ids), window)


@app.get("/api/weapons")
def weapons(player_ids: str | None = None, monster_id: int | None = None,
            stars: int | None = None, db: Session = Depends(get_db)):
    return queries.weapon_matrix(db, queries._parse_ids(player_ids), monster_id, stars)


@app.get("/api/hunts/{hunt_id}/curve")
def curve(hunt_id: int, max_points: int = 500, db: Session = Depends(get_db)):
    try:
        return queries.hunt_curve(db, hunt_id, max_points)
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
            stars: int | None = None, db: Session = Depends(get_db)):
    return queries.synergy(db, queries._parse_ids(player_ids), monster_id, stars)


@app.get("/api/quests")
def quests(db: Session = Depends(get_db)):
    return queries.quest_stats(db)


@app.get("/api/records")
def records(db: Session = Depends(get_db)):
    return queries.records(db)


@app.get("/api/high-scores")
def high_scores(player_id: int | None = None, monster_id: int | None = None,
                weapon_id: int | None = None, stars: int | None = None,
                sort_by: str = "time", db: Session = Depends(get_db)):
    return queries.high_scores(db, player_id, monster_id, weapon_id, stars, sort_by)


@app.get("/api/activity")
def activity(db: Session = Depends(get_db)):
    return queries.activity(db)


@app.get("/api/compare")
def compare(player_ids: str | None = None, window: int = 5,
            db: Session = Depends(get_db)):
    return queries.compare(db, queries._parse_ids(player_ids), window)


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
