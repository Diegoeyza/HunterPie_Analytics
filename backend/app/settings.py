"""User settings persisted beside the DB (survive in-place app updates).

Only settings the API process needs belong here; purely visual preferences
stay in the dashboard's localStorage. The file is intentionally small and
fail-soft: a missing or corrupt config must never block ingestion.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from .paths import user_data_dir

log = logging.getLogger(__name__)

SETTINGS_FILE = "config.json"
MAX_EXPORT_DIRS = 20

#: DPS divisor window. ``engagement`` (default) divides by active fighting
#: time (own first hit -> own last hit); ``quest`` divides by first hit ->
#: quest end (HunterPie quest time), so post-kill downtime dilutes the number.
DPS_WINDOW_ENGAGEMENT = "engagement"
DPS_WINDOW_QUEST = "quest"
DPS_WINDOWS = frozenset({DPS_WINDOW_ENGAGEMENT, DPS_WINDOW_QUEST})


def settings_path() -> Path:
    """Writable config path, beside ``$HUNTS_DB`` when that is set.

    The packaged app already points ``HUNTS_DB`` at the per-user data dir, so
    this keeps desktop behavior and also persists settings in Docker, where
    only the database directory is mounted.
    """
    db = os.environ.get("HUNTS_DB")
    if db:
        return Path(db).expanduser().resolve().parent / SETTINGS_FILE
    return user_data_dir() / SETTINGS_FILE


def _defaults() -> dict:
    return {"export_dirs": [], "dps_window": DPS_WINDOW_ENGAGEMENT}


def load_settings(path: Path | None = None) -> dict:
    """Read the settings dict, returning defaults when unavailable.

    Unknown ``dps_window`` values fall back to ``engagement`` (never crash
    on a hand-edited config)."""
    path = path or settings_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _defaults()
    except (OSError, ValueError) as e:
        log.warning("could not read settings %s: %s", path, e)
        return _defaults()
    if not isinstance(raw, dict):
        return _defaults()
    dirs = raw.get("export_dirs")
    window = raw.get("dps_window", DPS_WINDOW_ENGAGEMENT)
    return {
        "export_dirs": [d for d in dirs if isinstance(d, str)]
        if isinstance(dirs, list) else [],
        "dps_window": window if window in DPS_WINDOWS else DPS_WINDOW_ENGAGEMENT,
    }


def save_settings(data: dict, path: Path | None = None) -> None:
    """Atomically write the settings dict (temp file + replace)."""
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def configured_export_dirs(path: Path | None = None) -> list[Path]:
    """Extra HuntExports folders added by the user (may not exist)."""
    return [Path(d) for d in load_settings(path)["export_dirs"]]


def dps_window(path: Path | None = None) -> str:
    """Active DPS divisor window (``engagement`` or ``quest``)."""
    return load_settings(path)["dps_window"]
