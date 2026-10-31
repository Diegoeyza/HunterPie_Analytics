"""Monster status ids stored in ``monster_events`` -> display metadata.

The HunterPie companion exports status activations as ``AILMENT_*`` ids. The
importer normalizes them to ``ailment.<name>`` (enrage stays ``enrage``) so the
event types are stable across game versions and readable in the database.
"""
from __future__ import annotations

from collections.abc import Iterable

ENRAGE = "enrage"
_AILMENT_PREFIX = "ailment."

#: HunterPie ids whose display name is not the plain title-cased tail.
_DISPLAY_NAMES = {
    "ailment.dung": "Dung Bomb",
    "ailment.powerclash": "Power Clash",
}


def display_name(event_type: str) -> str:
    """Human label for an event type (enrage or ``ailment.<name>``)."""
    if event_type == ENRAGE:
        return "Enrage"
    known = _DISPLAY_NAMES.get(event_type)
    if known:
        return known
    tail = event_type.removeprefix(_AILMENT_PREFIX).replace("_", " ").strip()
    return tail.title() if tail else event_type


def kind(event_type: str) -> str:
    """Grouping used by the dashboard (the monster has one "buff" only)."""
    return "Enrage" if event_type == ENRAGE else "Ailment"


def merge_windows(
    spans: Iterable[tuple[float, float | None]],
) -> list[dict]:
    """Merge overlapping spans so uptime can never double-count.

    ``end=None`` means "still active at quest end" and absorbs every following
    span of the same status. Input order does not matter.
    """
    merged: list[dict] = []
    for start, end in sorted(spans, key=lambda span: span[0]):
        if merged and (merged[-1]["end"] is None
                       or start <= merged[-1]["end"]):
            prev = merged[-1]
            if prev["end"] is not None and end is not None and end > prev["end"]:
                prev["end"] = end
            continue
        merged.append({"start": start, "end": end})
    return merged
