"""Shared query plumbing: id parsing, visibility, party filter, bounds.

All dashboard metric queries funnel hunt selection through these helpers
so scope/party/visibility semantics stay identical across tabs.
"""
from __future__ import annotations

from .models import Hunt

MAX_LIMIT = 2000
MAX_POINTS = 5000
MAX_WINDOW = 60
MAX_TOP_N = 25
MAX_PARTY = 8


class FilterError(ValueError):
    """Invalid filter input from the client (mapped to HTTP 422)."""


def parse_ids(raw: str | None) -> list[int]:
    """Strict comma-separated id list. Garbage segments raise FilterError
    (the old silent-ignore hid broken dashboard params)."""
    if raw is None or not raw.strip():
        return []
    ids = []
    for seg in raw.split(","):
        seg = seg.strip()
        if not seg:
            continue
        if not seg.isdigit():
            raise FilterError(f"invalid player id: {seg!r}")
        ids.append(int(seg))
    return ids


def visible():
    """Filter for user-visible hunts (NULL-safe: pre-flag rows are NULL)."""
    return Hunt.ignored.isnot(True)


def party(stmt, size: int | None):
    """Narrow a Hunt-selecting statement to hunts with exactly N players.

    ``size`` is the global party-size filter (Hunt.player_count, the same
    number the Hunts tab shows). None = all party sizes.
    """
    if size is None:
        return stmt
    if not 1 <= size <= MAX_PARTY:
        raise FilterError(f"invalid party size: {size!r}")
    return stmt.where(Hunt.player_count == size)


def check_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    if not 1 <= limit <= MAX_LIMIT:
        raise FilterError(f"limit must be 1..{MAX_LIMIT}, got {limit!r}")
    return limit


def check_window(window: int) -> int:
    if not 1 <= window <= MAX_WINDOW:
        raise FilterError(f"window must be 1..{MAX_WINDOW}, got {window!r}")
    return window


def check_max_points(max_points: int) -> int:
    if not 1 <= max_points <= MAX_POINTS:
        raise FilterError(f"max_points must be 1..{MAX_POINTS}, got {max_points!r}")
    return max_points
