"""Engine/session helpers. SQLite file lives on the native filesystem (never /mnt/c)."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "hunts.db"

# Pre-Alembic lightweight migration: columns added here are backfilled onto
# existing DBs. (PLAN called for Alembic from day one; until then this keeps
# `init_db` safe to call on any V1 database.)
HUNTS_EXTRA_COLUMNS = [
    ("quest_id", "INTEGER"),
    ("quest_type", "INTEGER"),
    ("quest_level", "INTEGER"),
    ("quest_stars", "INTEGER"),
    ("monster_max_hp", "REAL"),
    ("monster_variant", "INTEGER"),
    ("monster_crown", "INTEGER"),
]


def make_engine(db_path: str | Path = DEFAULT_DB_PATH, echo: bool = False):
    return create_engine(f"sqlite:///{db_path}", echo=echo, future=True)


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    engine = make_engine(db_path)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        existing = {r[1] for r in conn.execute(text("PRAGMA table_info(hunts)"))}
        for name, ddl in HUNTS_EXTRA_COLUMNS:
            if name not in existing:
                conn.execute(text(f"ALTER TABLE hunts ADD COLUMN {name} {ddl}"))
    engine.dispose()


def make_session(db_path: str | Path = DEFAULT_DB_PATH) -> Session:
    return sessionmaker(bind=make_engine(db_path), future=True)()
