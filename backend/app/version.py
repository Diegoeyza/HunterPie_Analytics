"""Single source of truth for the app version + release coordinates.

Bump ``APP_VERSION`` together with the other version carriers:
  - installer/HunterPieAnalytics.iss   (#define AppVersion)
  - packaging/version_info.txt
  - packaging/msix/AppxManifest.xml
The in-app updater (``app.updater``) compares this against the latest GitHub
release; the dashboard shows it in Settings.
"""
from __future__ import annotations

import re
from functools import lru_cache

from .paths import resource_path

APP_VERSION = "1.0.10"
GITHUB_REPO = "Diegoeyza/HunterPie_Analytics"
RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases"

# The installer copies hunt_dumper.lua to <app>\HuntDumper and PyInstaller
# bundles it under reframework/, so the app always knows which mod release it
# ships. Dumps record the same value in `mod_version`, letting the dashboard
# tell the user to reinstall the mod after an app update.
_MOD_FILE = resource_path("reframework", "hunt_dumper.lua")
_MOD_VERSION_RE = re.compile(r'^local VERSION = "([^"]+)"', re.M)


@lru_cache(maxsize=1)
def bundled_mod_version() -> str | None:
    try:
        text = _MOD_FILE.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _MOD_VERSION_RE.search(text)
    return m.group(1) if m else None


def version_tuple(text: str | None) -> tuple[int, ...]:
    """Numeric parts of a dotted version, for equality/order checks only."""
    if not text:
        return ()
    return tuple(int(p) for p in re.findall(r"\d+", text))


def version_lt(a: str | None, b: str | None) -> bool:
    """True when a < b, padding missing parts ("0.11" == "0.11.0")."""
    ta, tb = version_tuple(a), version_tuple(b)
    if not ta or not tb:
        return False
    size = max(len(ta), len(tb))
    return (ta + (0,) * (size - len(ta))) < (tb + (0,) * (size - len(tb)))
