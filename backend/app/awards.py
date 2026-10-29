"""Support All-Star (award 0) attribution.

Award 0 ("Buffs and Heals Applied") is exported as a ``UInt32[4]`` *row* per
party member, indexed by the party position of the hunter who applied the
support: a row is what that member *received* from each one (its diagonal is
self-support). The game credits the applier once per hunter affected — i.e. the
applier's *column* — so a player's count is the sum of their column across the
party, while the row sum is "support received".

Only the party order is needed, and the dump exports rows in party order, so
this works from the dump itself. ``support_slots`` also copes with a party that
had a slot gap (a hunter took a free slot), where a cell can sit outside the
row range.
"""
from __future__ import annotations

SUPPORT_AWARD_ID = 0
_CHANNELS = 4


def support_slots(rows: list[list[int]]) -> list[int]:
    """Party position of each row of the award-0 matrix.

    Rows are exported in ascending party order, so row *i* is position *i*. A
    cell in a column no row can own means the quest used a non-contiguous set
    of slots, so the occupied columns say which positions are in play (a hunter
    who applied nothing leaves no cell, so the rest is filled in ascending
    order — those columns are all zero, so it cannot change a count).
    """
    n = len(rows)
    if not n:
        return []
    occupied = [i for i in range(_CHANNELS)
                if any(i < len(r) and r[i] for r in rows)]
    if any(i >= n for i in occupied):
        slots = sorted(occupied)[:n]
        if len(slots) < n:
            slots += [i for i in range(_CHANNELS) if i not in slots][:n - len(slots)]
            slots.sort()
        return slots
    return list(range(n))


def support_applied(rows: list[list[int]]) -> list[float]:
    """Buffs/heals applied by each row's hunter (their column sum)."""
    slots = support_slots(rows)
    return [float(sum(r[s] if s < len(r) else 0 for r in rows)) for s in slots]


def support_rows(players: list[dict]) -> list[list[int]]:
    """Award-0 channel rows from a dump's player list, in party order.

    Empty when no player carries a channel row: solo hunts export the game's
    own scalar (``get_QuestAwardInfo``) instead, and there is no party to split.
    """
    rows: list[list[int]] = []
    any_channels = False
    for p in players:
        ch = None
        for a in p.get("awards") or []:
            if a.get("id") is not None and int(a["id"]) == SUPPORT_AWARD_ID:
                ch = a.get("channels")
                break
        if ch:
            any_channels = True
        rows.append([int(v or 0) for v in (ch or [])][:_CHANNELS])
    return rows if any_channels else []
