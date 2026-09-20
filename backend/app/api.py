"""FastAPI dashboard API + import hook.

Run:  cd backend && ../.venv/bin/python -m app.api   (serves :8000)
DB:   $HUNTS_DB or backend/hunts.db. Port: $PORT or 8000.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import queries
from .db import DEFAULT_DB_PATH, init_db, make_session
from .filters import (
    MAX_LIMIT,
    MAX_PARTY,
    MAX_POINTS,
    MAX_TOP_N,
    MAX_WINDOW,
    FilterError,
    parse_ids,
)
from .import_hunt import DEFAULT_EXPORTS_DIR
from .import_job import JobBusyError, cancel_job, get_job, start_import_job

log = logging.getLogger(__name__)

DB_PATH = Path(os.environ.get("HUNTS_DB", DEFAULT_DB_PATH))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # New tables/columns (e.g. player_aliases) must exist before the first
    # request: a plain `python -m app.api` boot never ran init_db, so fresh
    # code against an old DB 500'd on missing tables. Idempotent.
    init_db(DB_PATH)
    yield

# Local dev serves the dashboard on varying ports (:3000 dev, :3001 prod
# preview). Extra origins can be appended via $CORS_ORIGINS (comma-sep).
# NOTE: this Starlette version rejects allow_origins=None — always pass a
# real list and use allow_origin_regex for the localhost range.
_extra = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app = FastAPI(title="HunterPie Analytics", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", *dict.fromkeys(_extra)],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    # make_session reuses the shared cached Engine per DB path (db.py) —
    # per-request cost is one connection checkout, not a new pool.
    session = make_session(DB_PATH)
    try:
        yield session
    finally:
        session.close()


def _ids(raw: str | None) -> list[int]:
    try:
        return parse_ids(raw)
    except FilterError as e:
        raise HTTPException(422, str(e)) from None


def _party(size: int | None) -> int | None:
    if size is not None and not 1 <= size <= MAX_PARTY:
        raise HTTPException(422, f"players must be 1..{MAX_PARTY}")
    return size


class IgnoreBody(BaseModel):
    ignored: bool = True


class LabelBody(BaseModel):
    label: str | None = Field(default=None, max_length=120)


@app.get("/api/filter-options")
def filter_options(db: Session = Depends(get_db)):
    return queries.filter_options(db)


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    return queries.health(db)


@app.get("/api/hunts")
def hunts(limit: int = Query(200, ge=1, le=MAX_LIMIT),
          include_ignored: bool = False,
          player_ids: str | None = None, players: int | None = None,
          db: Session = Depends(get_db)):
    return queries.hunt_list(db, limit, include_ignored,
                             _ids(player_ids), party=_party(players))


@app.get("/api/progress")
def progress(monster_id: int | None = None, weapon_id: int | None = None,
             player_id: int | None = None, quest_id: int | None = None,
             stars: int | None = None, player_ids: str | None = None,
             window: int = Query(5, ge=1, le=MAX_WINDOW),
             variant_id: str | None = None,
             limit: int | None = Query(None, ge=1, le=MAX_LIMIT),
             players: int | None = None,
             db: Session = Depends(get_db)):
    return queries.progress(db, monster_id, weapon_id, player_id,
                            quest_id, stars, _ids(player_ids),
                            window, variant_id, limit, party=_party(players))


@app.get("/api/progress/improvement")
def progress_improvement(player_id: int | None = None,
                         top_n: int = Query(5, ge=1, le=MAX_TOP_N),
                         weapon_id: int | None = None,
                         player_ids: str | None = None,
                         monster_id: int | None = None,
                         stars: int | None = None,
                         variant_id: str | None = None,
                         players: int | None = None,
                         db: Session = Depends(get_db)):
    return queries.progress_improvement(db, player_id, top_n, weapon_id,
                                        _ids(player_ids),
                                        monster_id, stars, variant_id,
                                        party=_party(players))



@app.get("/api/weapons")
def weapons(player_ids: str | None = None, monster_id: int | None = None,
            stars: int | None = None, variant_id: str | None = None,
            players: int | None = None,
            db: Session = Depends(get_db)):
    return queries.weapon_matrix(db, _ids(player_ids), monster_id,
                                 stars, variant_id, party=_party(players))


@app.get("/api/hunts/{hunt_id}/curve")
def curve(hunt_id: int, max_points: int = Query(500, ge=1, le=MAX_POINTS),
          quest_hp: bool = False,
          db: Session = Depends(get_db)):
    try:
        return queries.hunt_curve(db, hunt_id, max_points, quest_hp)
    except KeyError:
        raise HTTPException(404, f"hunt {hunt_id} not found") from None


@app.get("/api/hunts/{hunt_id}/abnormalities")
def abnormalities(hunt_id: int, db: Session = Depends(get_db)):
    try:
        return queries.hunt_abnormalities(db, hunt_id)
    except KeyError:
        raise HTTPException(404, f"hunt {hunt_id} not found") from None


@app.get("/api/synergy")
def synergy(player_ids: str | None = None, monster_id: int | None = None,
            stars: int | None = None, variant_id: str | None = None,
            players: int | None = None,
            db: Session = Depends(get_db)):
    return queries.synergy(db, _ids(player_ids), monster_id,
                           stars, variant_id, party=_party(players))


@app.get("/api/quests")
def quests(players: int | None = None, db: Session = Depends(get_db)):
    return queries.quest_stats(db, party=_party(players))


@app.get("/api/quests/detail")
def quest_detail(key: str, players: int | None = None,
                 db: Session = Depends(get_db)):
    """One quest row as individual instances, each with hunter damage + DPS."""
    try:
        return queries.quest_hunts(db, key, party=_party(players))
    except KeyError:
        raise HTTPException(404, f"quest {key} not found") from None


@app.get("/api/records")
def records(players: int | None = None, db: Session = Depends(get_db)):
    return queries.records(db, party=_party(players))


@app.get("/api/high-scores")
def high_scores(player_ids: str | None = None, monster_id: int | None = None,
                weapon_id: int | None = None, stars: int | None = None,
                sort_by: Literal["dps", "time"] = "dps",
                limit: int | None = Query(None, ge=1, le=MAX_LIMIT),
                variant_id: str | None = None,
                include_ignored: bool = False, players: int | None = None,
                db: Session = Depends(get_db)):
    return queries.high_scores(db, _ids(player_ids), monster_id,
                               weapon_id, stars, sort_by, limit, variant_id,
                               include_ignored, party=_party(players))


@app.patch("/api/hunts/{hunt_id}/ignore")
def ignore_hunt(hunt_id: int, body: IgnoreBody, db: Session = Depends(get_db)):
    """Hide (ignored=true) or restore a hunt from every stat view."""
    try:
        return queries.set_hunt_ignored(db, hunt_id, body.ignored)
    except KeyError:
        raise HTTPException(404, f"hunt {hunt_id} not found") from None


@app.get("/api/leaderboard")
def leaderboard(player_ids: str | None = None,
                monster_id: int | None = None, stars: int | None = None,
                weapon_id: int | None = None, variant_id: str | None = None,
                min_hunts: int = Query(1, ge=1, le=1000),
                players: int | None = None,
                db: Session = Depends(get_db)):
    return queries.leaderboard(db, _ids(player_ids), monster_id,
                               stars, weapon_id, variant_id, min_hunts,
                               party=_party(players))


@app.get("/api/activity")
def activity(players: int | None = None, db: Session = Depends(get_db)):
    return queries.activity(db, party=_party(players))


@app.get("/api/compare")
def compare(player_ids: str | None = None,
            window: int = Query(5, ge=1, le=MAX_WINDOW),
            variant_id: str | None = None, players: int | None = None,
            db: Session = Depends(get_db)):
    return queries.compare(db, _ids(player_ids), window,
                           variant_id, party=_party(players))


@app.get("/api/players/aliases")
def aliases(db: Session = Depends(get_db)):
    """Rename-variant sightings awaiting review (ingest writes these)."""
    return queries.list_aliases(db)


@app.post("/api/players/aliases/{alias_id}/merge")
def merge_alias(alias_id: int, db: Session = Depends(get_db)):
    try:
        return queries.merge_alias(db, alias_id)
    except KeyError:
        raise HTTPException(404, f"alias {alias_id} not found") from None


@app.delete("/api/players/aliases/{alias_id}")
def dismiss_alias(alias_id: int, db: Session = Depends(get_db)):
    try:
        return queries.dismiss_alias(db, alias_id)
    except KeyError:
        raise HTTPException(404, f"alias {alias_id} not found") from None


@app.get("/api/players/{player_id}/variants")
def player_variants(player_id: int, db: Session = Depends(get_db)):
    return queries.player_variants(db, player_id)


@app.patch("/api/weapon-identities/{identity_id}")
def rename_identity(identity_id: int, body: LabelBody,
                    db: Session = Depends(get_db)):
    try:
        return queries.set_identity_label(db, identity_id, body.label)
    except KeyError:
        raise HTTPException(404, f"weapon identity {identity_id} not found") from None


def _session_db_path(db: Session) -> Path:
    """DB file behind a request session (honors test dependency overrides)."""
    try:
        return Path(str(db.get_bind().url.database))
    except Exception:
        return DB_PATH


@app.post("/api/import", status_code=202)
def import_hunts(db: Session = Depends(get_db), force: bool = False):
    """Start a background HuntExports import; poll /api/import/status.

    The skip manifest means repeat runs only stat files (no parsing), so
    importing 1 new hunt costs ~1 file of work. force=True ignores the
    manifest and rechecks every file (e.g. after deleting hunts from the
    dashboard, which the manifest otherwise keeps deleted).
    A second POST while a job runs gets 409 (single-flight).
    """
    src = Path(os.environ.get("HUNT_EXPORTS", str(DEFAULT_EXPORTS_DIR)))
    if not src.is_dir():
        raise HTTPException(404, f"hunt exports dir not found: {src}")
    try:
        job = start_import_job(_session_db_path(db), src, force=force)
    except JobBusyError as e:
        raise HTTPException(409, str(e)) from None
    return {"job_id": job.job_id, "state": job.state, "total": job.total}


@app.post("/api/import/cancel")
def import_cancel(job_id: str | None = None):
    """Cancel a running import job (it stops after the current file)."""
    job = cancel_job(job_id)
    if job is None:
        raise HTTPException(404, "no import job found")
    return {"job_id": job.job_id, "state": job.state}


@app.get("/api/import/status")
def import_status(job_id: str | None = None):
    """Progress of an import job (or the latest one when omitted)."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "no import job found")
    return job.to_dict()


@app.get("/api/players/pins")
def pins(db: Session = Depends(get_db)):
    return queries.list_pins(db)


@app.post("/api/players/{player_id}/pin")
def pin(player_id: int, db: Session = Depends(get_db)):
    try:
        return queries.set_pin(db, player_id, True)
    except KeyError:
        raise HTTPException(404, f"player {player_id} not found") from None


@app.delete("/api/players/{player_id}/pin")
def unpin(player_id: int, db: Session = Depends(get_db)):
    try:
        return queries.set_pin(db, player_id, False)
    except KeyError:
        raise HTTPException(404, f"player {player_id} not found") from None


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run("app.api:app", host="127.0.0.1",
                port=int(os.environ.get("PORT", 8000)))
