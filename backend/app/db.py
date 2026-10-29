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

import json
import logging
import threading
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import create_engine, delete, event, select, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base
from .paths import is_frozen, user_data_dir

log = logging.getLogger(__name__)

if is_frozen():
    # The install dir is read-only for standard users; keep the DB (and WAL)
    # under %LOCALAPPDATA%\HunterPieAnalytics\.
    DEFAULT_DB_PATH = user_data_dir() / "hunts.db"
else:
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

LATEST_VERSION = 10


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


def dispose_engine(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Close and forget the cached Engine for a path.

    The cache keeps pooled connections open for the process lifetime, which
    pins the DB file — fine for the app, but tests (or any short-lived
    writer) must call this before deleting a DB file: Windows refuses to
    unlink a file a live Engine still holds open (WinError 32).
    """
    key = str(Path(db_path).expanduser().absolute())
    with _ENGINES_LOCK:
        engine = _ENGINES.pop(key, None)
    if engine is not None:
        engine.dispose()


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


def _migrate_v3(conn) -> None:
    """Per-hunt weapon model name (REFramework mod: weapon id -> localized)."""
    _add_missing_columns(conn, "hunt_players", [
        ("weapon_name", "TEXT"),
    ])


def _migrate_v6(conn) -> None:
    """Tag each hunt with its authoritative source.

    HunterPie owns damage/weapons/curves; the REFramework mod only adds awards,
    so a hunt whose awards came from the mod was created by it."""
    _add_missing_columns(conn, "hunts", [
        ("source", "TEXT NOT NULL DEFAULT 'hunterpie'"),
    ])
    conn.execute(text(
        "UPDATE hunts SET source='reframework' WHERE id IN "
        "(SELECT DISTINCT hunt_id FROM hunt_player_awards)"))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_hunts_source ON hunts (source)"))


def _migrate_v7(conn) -> None:
    """Re-add hunt_players.weapon_name (LOCAL player only).

    Reintroduced deliberately: the mod's weapon id->name lookup is reliable,
    but its per-player map is not, so only the local player's weapon name is
    recorded — enough for a hunter-scoped weapon-name filter."""
    _add_missing_columns(conn, "hunt_players", [
        ("weapon_name", "TEXT"),
    ])


def _migrate_v8(conn) -> None:
    """Per-player HP samples (Survival tab). New table: create_all covers
    fresh DBs; this backfills existing ones."""
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS player_health_steps ("
        "id INTEGER PRIMARY KEY, "
        "hunt_id INTEGER NOT NULL REFERENCES hunts(id) ON DELETE CASCADE, "
        "player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE, "
        "ts_offset_seconds REAL NOT NULL, "
        "hp_fraction REAL NOT NULL, "
        "red_fraction REAL, "
        "max_hp REAL)"))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_playerhp_hunt_player_ts "
        "ON player_health_steps (hunt_id, player_id, ts_offset_seconds)"))


def _migrate_v9(conn) -> None:
    """HuntDumper version recorded by the dump (mod-only hunts).

    The dashboard compares the newest value with the mod bundled in the app
    and prompts a reinstall after an update."""
    _add_missing_columns(conn, "hunts", [
        ("mod_version", "TEXT"),
    ])


def _migrate_v10(conn) -> None:
    """Support All-Star: credit the buffs/heals a player *applied*.

    Award 0 was stored as the sum of the player's own uint32[4] row, which is
    the support they *received* (their row is what each party member gave
    them). The game credits the applier once per hunter affected, i.e. that
    player's column in the party matrix. Rebuild the counts from the channels
    we already store; the insertion order of the award rows is the party order
    the mod exported (verified against every mod dump on disk)."""
    rows = conn.execute(text(
        "SELECT hunt_id, player_id, channels FROM hunt_player_awards "
        "WHERE award_id = 0 AND channels IS NOT NULL "
        "ORDER BY hunt_id, rowid"
    )).all()
    per_hunt: dict[int, list[tuple[int, list[int]]]] = {}
    for hunt_id, player_id, channels in rows:
        try:
            ch = [int(v or 0) for v in json.loads(channels)][:4]
        except (TypeError, ValueError):
            continue
        per_hunt.setdefault(hunt_id, []).append((player_id, ch))

    params = []
    for hunt_id, entries in per_hunt.items():
        for pos, (player_id, _ch) in enumerate(entries):
            applied = sum(ch[pos] if pos < len(ch) else 0 for _, ch in entries)
            params.append({"count": float(applied), "hunt_id": hunt_id,
                           "player_id": player_id})
    if params:
        conn.execute(text(
            "UPDATE hunt_player_awards SET count = :count "
            "WHERE hunt_id = :hunt_id AND player_id = :player_id "
            "AND award_id = 0"), params)


# v4/v5 (the REFramework weapon-model experiment) were reverted before release;
# their tables/columns never existed in a shipped DB, so those versions are
# intentionally absent. migrate() tolerates the gap in the sequence.
MIGRATIONS: dict[int, object] = {1: _migrate_v1, 2: _migrate_v2, 3: _migrate_v3,
                                 6: _migrate_v6, 7: _migrate_v7,
                                 8: _migrate_v8, 9: _migrate_v9,
                                 10: _migrate_v10}


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


def purge_mod_abnormalities(session: Session) -> int:
    """Delete buff rows left by the retired REFramework buff export.

    Buffs are companion-only now, so rows written by the mod are stale. A hunt
    whose ``source`` is ``reframework`` never received a companion dump (a
    companion import rewrites the source), so every abnormality row on such a
    hunt came from the mod. Opt-in and destructive: run once after upgrading.
    """
    from .models import Hunt, PlayerAbnormality

    mod_only_hunts = select(Hunt.id).where(Hunt.source == "reframework")
    deleted = session.execute(
        delete(PlayerAbnormality)
        .where(PlayerAbnormality.hunt_id.in_(mod_only_hunts))
    ).rowcount
    session.commit()
    return deleted

