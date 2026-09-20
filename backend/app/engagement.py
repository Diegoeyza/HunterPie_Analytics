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


def hunt_duration_s(hunt: Hunt) -> float | None:
    for candidate in (hunt.quest_time_seconds, hunt.real_hunt_time_seconds):
        if candidate:
            return float(candidate)
    if hunt.started_at and hunt.ended_at:
        return (hunt.ended_at - hunt.started_at).total_seconds() or None
    return None


def engagement_duration_s(session: Session, hunt_id: int) -> float | None:
    """First-hit to monster-death window for DPS.
    Death time = last monster HP step. Falls back to last snapshot,
    then to total hunt duration."""
    first = session.execute(
        select(func.min(DpsSnapshot.ts_offset_seconds))
        .where(DpsSnapshot.hunt_id == hunt_id)
    ).scalar()
    death = session.execute(
        select(func.max(MonsterHealthStep.ts_offset_seconds))
        .where(MonsterHealthStep.hunt_id == hunt_id)
    ).scalar()
    if first is not None and death is not None and death > first:
        return death - first
    # fallback: last damage snapshot
    last = session.execute(
        select(func.max(DpsSnapshot.ts_offset_seconds))
        .where(DpsSnapshot.hunt_id == hunt_id)
    ).scalar()
    if first is not None and last is not None and last > first:
        return last - first
    return hunt_duration_s(session.get(Hunt, hunt_id))


def player_engagement_s(session: Session, hunt_id: int,
                        player_id: int) -> float | None:
    """Active window for one hunter: own first->last damage snapshot.

    Handles mid-fight (SOS) joins, where the party-wide window would
    misattribute DPS: a late joiner's damage must be divided by their own
    time in the fight, not by first-hit->death. Falls back to the
    hunt-wide window when the hunter has fewer than two snapshots."""
    first, last = session.execute(
        select(func.min(DpsSnapshot.ts_offset_seconds),
               func.max(DpsSnapshot.ts_offset_seconds))
        .where(DpsSnapshot.hunt_id == hunt_id,
               DpsSnapshot.player_id == player_id)
    ).one()
    if first is not None and last is not None and last > first:
        return last - first
    return engagement_duration_s(session, hunt_id)


def batch_engagement_s(
    session: Session,
    hunts_by_id: dict[int, Hunt],
    pairs: list[tuple[int, int]],
) -> dict[tuple[int, int], float | None]:
    """Batched player_engagement_s for many (hunt, player) pairs.

    3 GROUP BY queries total regardless of pair count (vs up to 4 queries
    per pair unbatched): per-(hunt,player) snapshot min/max, per-hunt
    snapshot min/max, per-hunt monster-death (max HP step). Hunt-duration
    fallback comes from the already-loaded Hunt objects — no extra query.
    Semantics match player_engagement_s exactly.
    """
    if not pairs or not hunts_by_id:
        return {}
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
            if first is not None and last is not None and last > first:
                out[(hid, pid)] = last - first
                continue
        # hunt-wide fallback (mirrors engagement_duration_s)
        h_first, h_last = snap.get(hid, (None, None))
        death = deaths.get(hid)
        if h_first is not None and death is not None and death > h_first:
            out[(hid, pid)] = death - h_first
        elif h_first is not None and h_last is not None and h_last > h_first:
            out[(hid, pid)] = h_last - h_first
        else:
            hunt = hunts_by_id.get(hid)
            out[(hid, pid)] = hunt_duration_s(hunt) if hunt is not None else None
    return out
