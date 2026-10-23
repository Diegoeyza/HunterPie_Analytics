"""Engagement windows: the DPS divisor (first-hit to monster-death).

DPS = total_damage / engagement window. The window is per-player (own
first->last damage snapshot) with fallback to the hunt-wide window
(first snapshot -> monster death -> last snapshot -> hunt duration),
so mid-fight (SOS) joiners aren't misattributed party-wide DPS.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import DpsSnapshot, Hunt, MonsterHealthStep
from .settings import DPS_WINDOW_QUEST, dps_window as configured_dps_window


def hunt_duration_s(hunt: Hunt) -> float | None:
    for candidate in (hunt.quest_time_seconds, hunt.real_hunt_time_seconds):
        if candidate:
            return float(candidate)
    if hunt.started_at and hunt.ended_at:
        return (hunt.ended_at - hunt.started_at).total_seconds() or None
    return None


def _hunt_wide_window(h_first: float | None, h_last: float | None,
                      death: float | None,
                      quest_end: float | None,
                      hunt: Hunt | None,
                      window: str) -> float | None:
    """Shared hunt-wide fallback: quest end, monster death, last snapshot,
    then total hunt duration (mirrors engagement_duration_s)."""
    if window == DPS_WINDOW_QUEST and h_first is not None:
        end = max([q for q in (quest_end, h_last) if q is not None],
                  default=None)
        if end is not None and end > h_first:
            return end - h_first
    if h_first is not None and death is not None and death > h_first:
        return death - h_first
    if h_first is not None and h_last is not None and h_last > h_first:
        return h_last - h_first
    return hunt_duration_s(hunt) if hunt is not None else None


def engagement_duration_s(session: Session, hunt_id: int,
                           window: str | None = None) -> float | None:
    """First-hit to monster-death window for DPS.
    Death time = last monster HP step. Falls back to last snapshot,
    then to total hunt duration.

    ``window="quest"`` ends at the quest clock instead (HunterPie quest
    time). ``None`` follows the ``dps_window`` setting."""
    window = window or configured_dps_window()
    first = session.execute(
        select(func.min(DpsSnapshot.ts_offset_seconds))
        .where(DpsSnapshot.hunt_id == hunt_id)
    ).scalar()
    death = session.execute(
        select(func.max(MonsterHealthStep.ts_offset_seconds))
        .where(MonsterHealthStep.hunt_id == hunt_id)
    ).scalar()
    # fallback: last damage snapshot
    last = session.execute(
        select(func.max(DpsSnapshot.ts_offset_seconds))
        .where(DpsSnapshot.hunt_id == hunt_id)
    ).scalar()
    hunt = session.get(Hunt, hunt_id)
    quest_end = hunt_duration_s(hunt) if hunt is not None else None
    return _hunt_wide_window(first, last, death, quest_end, hunt, window)


def player_engagement_s(session: Session, hunt_id: int,
                        player_id: int,
                        window: str | None = None) -> float | None:
    """Active window for one hunter: own first->last damage snapshot.

    Handles mid-fight (SOS) joins, where the party-wide window would
    misattribute DPS: a late joiner's damage must be divided by their own
    time in the fight, not by first-hit->death. Falls back to the
    hunt-wide window when the hunter has fewer than two snapshots.

    ``window="quest"`` ends at the quest clock instead (HunterPie quest
    time): post-kill downtime dilutes the number. ``None`` follows the
    ``dps_window`` setting."""
    window = window or configured_dps_window()
    first, last = session.execute(
        select(func.min(DpsSnapshot.ts_offset_seconds),
               func.max(DpsSnapshot.ts_offset_seconds))
        .where(DpsSnapshot.hunt_id == hunt_id,
               DpsSnapshot.player_id == player_id)
    ).one()
    if window == DPS_WINDOW_QUEST and first is not None:
        hunt = session.get(Hunt, hunt_id)
        quest_end = hunt_duration_s(hunt) if hunt is not None else None
        # Clocks can disagree after a cross-source rebase (quest clock
        # shorter than the snapshot span): never end before the hunter's
        # own last hit, so quest mode only dilutes, never inflates.
        end = max([q for q in (quest_end, last) if q is not None],
                  default=None)
        if end is not None and end > first:
            return end - first
    if first is not None and last is not None and last > first:
        return last - first
    return engagement_duration_s(session, hunt_id, window=window)


def batch_engagement_s(
    session: Session,
    hunts_by_id: dict[int, Hunt],
    pairs: list[tuple[int, int]],
    window: str | None = None,
) -> dict[tuple[int, int], float | None]:
    """Batched player_engagement_s for many (hunt, player) pairs.

    3 GROUP BY queries total regardless of pair count (vs up to 4 queries
    per pair unbatched): per-(hunt,player) snapshot min/max, per-hunt
    snapshot min/max, per-hunt monster-death (max HP step). Hunt-duration
    and quest-end fallbacks come from the already-loaded Hunt objects —
    no extra query. Semantics match player_engagement_s exactly.

    ``window="quest"`` ends every window at the quest clock (HunterPie
    quest time). ``None`` follows the ``dps_window`` setting."""
    window = window or configured_dps_window()
    if not pairs or not hunts_by_id:
        return {}
    quest_ends: dict[int, float | None] = {
        hid: hunt_duration_s(h) for hid, h in hunts_by_id.items()
    }
    ids = list(hunts_by_id.keys())
    pp: dict[tuple[int, int], tuple] = {
        (hid, pid): (mn, mx)
        for hid, pid, mn, mx in session.execute(
            select(DpsSnapshot.hunt_id, DpsSnapshot.player_id,
                   func.min(DpsSnapshot.ts_offset_seconds),
                   func.max(DpsSnapshot.ts_offset_seconds))
            .where(DpsSnapshot.hunt_id.in_(ids))
            .group_by(DpsSnapshot.hunt_id, DpsSnapshot.player_id)
        ).all()
    }
    snap: dict[int, tuple] = {
        hid: (mn, mx)
        for hid, mn, mx in session.execute(
            select(DpsSnapshot.hunt_id,
                   func.min(DpsSnapshot.ts_offset_seconds),
                   func.max(DpsSnapshot.ts_offset_seconds))
            .where(DpsSnapshot.hunt_id.in_(ids))
            .group_by(DpsSnapshot.hunt_id)
        ).all()
    }
    deaths: dict[int, float] = {
        hid: mx
        for hid, mx in session.execute(
            select(MonsterHealthStep.hunt_id,
                   func.max(MonsterHealthStep.ts_offset_seconds))
            .where(MonsterHealthStep.hunt_id.in_(ids))
            .group_by(MonsterHealthStep.hunt_id)
        ).all()
    }
    out: dict[tuple[int, int], float | None] = {}
    for hid, pid in set(pairs):
        mn_mx = pp.get((hid, pid))
        if mn_mx is not None:
            first, last = mn_mx
            if window == DPS_WINDOW_QUEST:
                end = max([q for q in (quest_ends.get(hid), last)
                           if q is not None], default=None)
                if first is not None and end is not None and end > first:
                    out[(hid, pid)] = end - first
                    continue
            if first is not None and last is not None and last > first:
                out[(hid, pid)] = last - first
                continue
        # hunt-wide fallback (mirrors engagement_duration_s)
        h_first, h_last = snap.get(hid, (None, None))
        death = deaths.get(hid)
        out[(hid, pid)] = _hunt_wide_window(
            h_first, h_last, death, quest_ends.get(hid),
            hunts_by_id.get(hid), window)
    return out
