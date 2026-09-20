"""Engine/session helpers. SQLite file lives on the native filesystem (never /mnt/c).

Design:
- One shared Engine per DB path (module-level cache). Creating an Engine
  per request (the old behavior) leaked pools and re-ran setup per call.
- Per-connection pragmas via a ``connect`` event listener, so EVERY
  connection gets WAL + busy_timeout + foreign_keys=ON — not just the
  ones opened inside init_db().
- Versioned migrations via PRAGMA user_version (no Alembic dependency for
  a single-user SQLite app). Each migration is idempotent; init_db runs
  create_all (new tables) + pending migrations (columns/indexes/backfills).
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

log = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "hunts.db"

# Pre-Alembic lightweight migration: columns added here are backfilled onto
# existing DBs. Kept as migration v1 content (see MIGRATIONS). New tables
# are handled by create_all; only new columns on existing tables need
# listing here.
EXTRA_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "hunts": [
        ("quest_id", "INTEGER"),
        ("quest_type", "INTEGER"),
        ("quest_level", "INTEGER"),
        ("quest_stars", "INTEGER"),
        ("monster_max_hp", "REAL"),
        ("monster_variant", "INTEGER"),
        ("monster_crown", "INTEGER"),
        ("ignored", "INTEGER NOT NULL DEFAULT 0"),
    ],
    "hunt_players": [
        ("gear_raw", "REAL"),
        ("gear_element", "REAL"),
        ("gear_affinity", "REAL"),
    ],
}

LATEST_VERSION = 2


def _sqlite_url(db_path: str | Path) -> str:
    # quote() keeps spaces/unicode in paths working (plain f-string URLs
    # break on Windows-style or space-containing paths).
    abs_posix = Path(db_path).expanduser().absolute().as_posix()
    return f"sqlite:///{quote(abs_posix, safe='/:')}"


def _on_connect(dbapi_conn, _conn_record) -> None:
    cur = dbapi_conn.cursor()
    try:
        # WAL: import writes must not block dashboard reads (the progress
        # poller reads while the background job writes). Native FS only.
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=10000")
        # Without this, ON DELETE CASCADE is a dead letter in SQLite.
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA synchronous=NORMAL")
    finally:
        cur.close()


_ENGINES: dict[str, object] = {}
_ENGINES_LOCK = threading.Lock()


def get_engine(db_path: str | Path = DEFAULT_DB_PATH):
    """Shared Engine for a DB path (cached, thread-safe)."""
    key = str(Path(db_path).expanduser().absolute())
    with _ENGINES_LOCK:
        engine = _ENGINES.get(key)
        if engine is None:
            # check_same_thread=False: FastAPI serves sync endpoints from a
            # worker thread pool and imports run on a background thread;
            # each thread uses its own session/connection.
            engine = create_engine(
                _sqlite_url(key), future=True,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
            event.listen(engine, "connect", _on_connect)
            _ENGINES[key] = engine
        return engine


def make_engine(db_path: str | Path = DEFAULT_DB_PATH, echo: bool = False):
    """Legacy entry point — now returns the shared cached Engine.

    ``echo`` only applies on first creation for a path.
    """
    engine = get_engine(db_path)
    engine.echo = echo
    return engine


def _user_version(conn) -> int:
    return conn.execute(text("PRAGMA user_version")).scalar_one()


def _set_user_version(conn, version: int) -> None:
    conn.execute(text(f"PRAGMA user_version={int(version)}"))


def _table_columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}


def _add_missing_columns(conn, table: str,
                         columns: list[tuple[str, str]]) -> None:
    existing = _table_columns(conn, table)
    for name, ddl in columns:
        if name not in existing:
            log.info("migrate: ALTER TABLE %s ADD COLUMN %s %s",
                     table, name, ddl)
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def _migrate_v1(conn) -> None:
    """Legacy EXTRA_COLUMNS backfill + engagement composite index."""
    for table, columns in EXTRA_COLUMNS.items():
        _add_missing_columns(conn, table, columns)
    # Backfill composite index for per-player engagement lookups
    # (filters on hunt_id + player_id).
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_snapshots_hunt_player "
        "ON dps_snapshots (hunt_id, player_id)"))


def _migrate_v2(conn) -> None:
    """Hot-filter indexes, identity columns, split-quest + warning columns."""
    for idx_sql in (
        "CREATE INDEX IF NOT EXISTS idx_hunts_quest ON hunts (quest_id)",
        "CREATE INDEX IF NOT EXISTS idx_hunts_stars ON hunts (quest_stars)",
        "CREATE INDEX IF NOT EXISTS idx_hunts_players ON hunts (player_count)",
        "CREATE INDEX IF NOT EXISTS idx_hunts_ignored ON hunts (ignored)",
        "CREATE INDEX IF NOT EXISTS idx_hunts_cleared ON hunts (cleared)",
        "CREATE INDEX IF NOT EXISTS idx_hunt_players_player "
        "ON hunt_players (player_id)",
        "CREATE INDEX IF NOT EXISTS idx_hunt_players_weapon "
        "ON hunt_players (weapon_id)",
        "CREATE INDEX IF NOT EXISTS idx_events_type "
        "ON monster_events (event_type)",
        "CREATE INDEX IF NOT EXISTS idx_abnormalities_hunt "
        "ON player_abnormalities (hunt_id)",
    ):
        try:
            conn.execute(text(idx_sql))
        except Exception as e:  # table may predate the feature; log, continue
            log.warning("migrate: %s failed: %s", idx_sql, e)
    _add_missing_columns(conn, "hunts", [
        ("quest_damage", "REAL"),
        ("is_split_quest", "INTEGER NOT NULL DEFAULT 0"),
    ])
    _add_missing_columns(conn, "players", [
        ("canonical", "TEXT"),
    ])
    _add_missing_columns(conn, "imported_files", [
        ("warnings_json", "TEXT"),
    ])
    # Backfill canonical names (lookup aid; duplicates stay — case
    # variants coexist until a human merges them, so no UNIQUE index).
    conn.execute(text(
        "UPDATE players SET canonical = lower(display_name) "
        "WHERE canonical IS NULL"))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_players_canonical "
        "ON players (canonical)"))


MIGRATIONS: dict[int, object] = {1: _migrate_v1, 2: _migrate_v2}


def migrate(engine=None, db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """Run pending migrations. Returns the resulting schema version."""
    engine = engine or get_engine(db_path)
    with engine.begin() as conn:
        current = _user_version(conn)
        for version in sorted(MIGRATIONS):
            if version > current:
                log.info("migrate: v%s -> v%s", current, version)
                MIGRATIONS[version](conn)
                _set_user_version(conn, version)
                current = version
    return current


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    migrate(engine)


def _session_factory(db_path: str | Path = DEFAULT_DB_PATH):
    return sessionmaker(bind=get_engine(db_path), future=True)


def make_session(db_path: str | Path = DEFAULT_DB_PATH) -> Session:
    return _session_factory(db_path)()
