"""In-app update check + installer download.

The desktop build is a per-user Inno Setup install with a stable AppId, and the
SQLite DB / settings live outside the install dir, so a newer release installs
in place over the running app with no UAC prompt. This module:

  * checks the latest GitHub release and semver-compares it to the running
    version,
  * locates the Setup ``.exe`` and its SHA256 in the release assets,
  * downloads + verifies the installer, and
  * (Windows) launches it silently so Inno replaces the app.

Network access is limited to the official release assets on github.com. Every
function that touches the network is kept separate from the pure parsing logic
so the latter is trivially testable without a connection.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from .version import APP_VERSION, RELEASE_API

USER_AGENT = "HunterPieAnalytics-Updater"
SETUP_PREFIX = "HunterPieAnalytics-Setup-"
SETUP_SUFFIX = ".exe"
SUMS_NAME = "SHA256SUMS.txt"
CHECK_TTL = 6 * 3600  # seconds a successful check is reused

# Release assets are served from github.com (redirects to these hosts).
_TRUSTED_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "github-releases.githubusercontent.com",
    "release-assets.githubusercontent.com",
}

_VER_RE = re.compile(r"(\d+(?:\.\d+)*)")


def parse_version(text: str) -> tuple[int, ...]:
    """'v1.0.10' / '1.0.10' -> (1, 0, 10); anything without digits -> ().

    Tuple comparison makes '1.0.10' > '1.0.9' (a plain string compare does not).
    """
    match = _VER_RE.search(text or "")
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def is_newer(latest: str, current: str) -> bool:
    """True when ``latest`` is a strictly higher version than ``current``."""
    return parse_version(latest) > parse_version(current)


def parse_sums(text: str) -> dict[str, str]:
    """SHA256SUMS.txt -> {filename: lowercase hex digest}.

    Tolerates the ``<digest>  <name>`` and ``<digest> *<name>`` (binary) forms.
    """
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, name = parts[0].strip().lower(), parts[1].strip().lstrip("*")
        out[name] = digest
    return out


def select_assets(release: dict) -> dict | None:
    """Pick the Setup .exe + the SHA256SUMS URL from a release JSON.

    Returns None when the release carries no installer (e.g. a fork-only tag).
    """
    setup: dict | None = None
    sums_url: str | None = None
    for asset in release.get("assets") or []:
        name = asset.get("name", "")
        if name.startswith(SETUP_PREFIX) and name.endswith(SETUP_SUFFIX):
            setup = asset
        elif name == SUMS_NAME:
            sums_url = asset.get("browser_download_url")
    if setup is None:
        return None
    return {
        "name": setup["name"],
        "url": setup.get("browser_download_url"),
        "size": setup.get("size"),
        "sums_url": sums_url,
    }


def is_trusted_url(url: str) -> bool:
    """Only download installers from GitHub's release hosts."""
    host = (urlparse(url).hostname or "").lower()
    return host in _TRUSTED_HOSTS


def describe_update(release: dict | None, current: str = APP_VERSION,
                    sha256: str | None = None) -> dict:
    """Shape the ``/api/update`` payload (also used when a check fails)."""
    info = {
        "current": current,
        "latest": None,
        "update_available": False,
        "url": None,
        "sha256": None,
        "size": None,
        "notes_url": None,
        "error": None,
    }
    if not release:
        return info
    tag = release.get("tag_name") or release.get("name") or ""
    latest = tag.lstrip("v")
    info["latest"] = latest or None
    info["notes_url"] = release.get("html_url")
    if not is_newer(tag, current):
        return info
    picked = select_assets(release)
    if not picked or not picked.get("url"):
        return info
    info["update_available"] = True
    info["url"] = picked["url"]
    info["size"] = picked["size"]
    info["sha256"] = sha256
    return info


# --- network -----------------------------------------------------------------

def _get(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json, text/plain, */*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def fetch_latest_release(timeout: float = 15.0) -> dict | None:
    """Latest stable (non-draft, non-prerelease) release JSON."""
    data = json.loads(_get(RELEASE_API, timeout).decode("utf-8"))
    if data.get("draft") or data.get("prerelease"):
        return None
    return data


_cache: dict = {"at": 0.0, "data": None}


def check_for_update(current: str = APP_VERSION, *, force: bool = False,
                     timeout: float = 15.0) -> dict:
    """Cached release check. Network/URL errors are reported, never raised."""
    now = time.time()
    if not force and _cache["data"] and now - _cache["at"] < CHECK_TTL:
        return dict(_cache["data"], current=current)
    try:
        release = fetch_latest_release(timeout)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return dict(describe_update(None, current), error=str(exc))
    sha = None
    picked = select_assets(release) if release else None
    if picked and picked.get("sums_url"):
        try:
            sums = parse_sums(_get(picked["sums_url"], timeout).decode("utf-8"))
            sha = sums.get(picked["name"])
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            sha = None
    info = describe_update(release, current, sha256=sha)
    _cache.update(at=now, data=info)
    return dict(info, current=current)


def download_asset(url: str, dest: Path, expected_sha256: str | None, *,
                   timeout: float = 120.0,
                   on_progress: Callable[[int, int], None] | None = None) -> Path:
    """Stream an asset to ``dest``, verifying SHA256 as it goes.

    Raises ValueError on a checksum mismatch (and removes the bad file).
    """
    digest = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    got = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as fh:  # noqa: S310
        total = int(resp.headers.get("Content-Length") or 0)
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            digest.update(chunk)
            got += len(chunk)
            if on_progress:
                on_progress(got, total)
    if expected_sha256 and digest.hexdigest() != expected_sha256.lower():
        dest.unlink(missing_ok=True)
        raise ValueError(f"checksum mismatch for {dest.name}")
    return dest


def launch_installer(path: Path) -> None:
    """Run the Inno Setup installer silently over the running app.

    ``/CLOSEAPPLICATIONS`` lets Restart Manager close the app + companion that
    hold files in {app}; ``/RESTARTAPPLICATIONS`` reopens them afterwards.
    """
    import subprocess

    subprocess.Popen(
        [str(path), "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
        close_fds=True,
    )
