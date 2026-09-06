"""Engine/session helpers. SQLite file lives on the native filesystem (never /mnt/c)."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "hunts.db"


def make_engine(db_path: str | Path = DEFAULT_DB_PATH, echo: bool = False):
    return create_engine(f"sqlite:///{db_path}", echo=echo, future=True)


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    engine = make_engine(db_path)
    Base.metadata.create_all(engine)
    engine.dispose()


def make_session(db_path: str | Path = DEFAULT_DB_PATH) -> Session:
    return sessionmaker(bind=make_engine(db_path), future=True)()
