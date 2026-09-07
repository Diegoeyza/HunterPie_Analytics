"""Engine/session helpers. SQLite file lives on the native filesystem (never /mnt/c)."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "hunts.db"

# Pre-Alembic lightweight migration: columns added here are backfilled onto
# existing DBs. (PLAN called for Alembic from day one; until then this keeps
# `init_db` safe to call on any V1 database.) New tables are handled by
# create_all above; only new columns on existing tables need listing here.
EXTRA_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "hunts": [
        ("quest_id", "INTEGER"),
        ("quest_type", "INTEGER"),
        ("quest_level", "INTEGER"),
        ("quest_stars", "INTEGER"),
        ("monster_max_hp", "REAL"),
        ("monster_variant", "INTEGER"),
        ("monster_crown", "INTEGER"),
    ],
    "hunt_players": [
        ("gear_raw", "REAL"),
        ("gear_element", "REAL"),
        ("gear_affinity", "REAL"),
    ],
}


def make_engine(db_path: str | Path = DEFAULT_DB_PATH, echo: bool = False):
    return create_engine(f"sqlite:///{db_path}", echo=echo, future=True)


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    engine = make_engine(db_path)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for table, columns in EXTRA_COLUMNS.items():
            existing = {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
    engine.dispose()


def make_session(db_path: str | Path = DEFAULT_DB_PATH) -> Session:
    return sessionmaker(bind=make_engine(db_path), future=True)()
