"""Runtime path helpers shared by the source run and the frozen desktop build.

When packaged with PyInstaller (onedir), read-only resources live under
``sys._MEIPASS`` while anything writable (the SQLite DB, config) must go to a
per-user location — the install directory is not writable for standard users.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "HunterPieAnalytics"


def is_frozen() -> bool:
    """True inside a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def resource_path(*parts: str) -> Path:
    """Read-only bundled resource (dashboard export, data files).

    Frozen: resolves under ``sys._MEIPASS``.
    Source: resolves from the repo root (this file is backend/app/paths.py).
    """
    if is_frozen():
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base.joinpath(*parts)


def user_data_dir() -> Path:
    """Writable per-user directory for the DB + config (created on demand)."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path
