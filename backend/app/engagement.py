"""DPS windows: the DPS divisor (own first hit to quest end).

DPS = total_damage / window. The window starts at each hunter's own first
damage snapshot — so mid-fight (SOS) joiners aren't misattributed
party-wide DPS — and ends at the party's last damage snapshot: the moment
the quest ended for everyone. That mirrors the in-game HunterPie meter
(``RelativeToFirstHit``): its quest timer runs to the results screen while
each hunter's own accumulated damage is divided by their own time in the
fight, so early-stoppers dilute exactly like the overlay shows.

``window="engagement"`` instead ends each window at the hunter's own last
hit (first-hit to last-hit), for per-hunter activity analysis. Both modes
fall back to the hunt-wide window, then to total hunt duration, when
snapshots are missing.
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
                      hunt: Hunt | None,
                      window: str) -> float | None:
    """Shared hunt-wide fallback: quest end (party last hit), else monster
    death, last snapshot, then total hunt duration
    (mirrors engagement_duration_s)."""
    if window == DPS_WINDOW_QUEST and h_first is not None:
        if h_last is not None and h_last > h_first:
            return h_last - h_first
    if h_first is not None and death is not None and death > h_first:
        return death - h_first
    if h_first is not None and h_last is not None and h_last > h_first:
        return h_last - h_first
    return hunt_duration_s(hunt) if hunt is not None else None


def engagement_duration_s(session: Session, hunt_id: int,
                           window: str | None = None) -> float | None:
    """Hunt-wide DPS window: first hit to quest end (party last hit).

    ``window="quest"`` ends at the party's last damage snapshot (quest
    end, shared by the whole party). ``window="engagement"`` prefers
    monster death (last HP step), then the last snapshot, then total hunt
    duration. ``None`` follows the ``dps_window`` setting."""
    window = window or configured_dps_window()
    first = session.execute(
        select(func.min(DpsSnapshot.ts_offset_seconds))
        .where(DpsSnapshot.hunt_id == hunt_id)
    ).scalar()
    death = session.execute(
        select(func.max(MonsterHealthStep.ts_offset_seconds))
        .where(MonsterHealthStep.hunt_id == hunt_id)
    ).scalar()
    # quest end = party last hit (max damage snapshot): the finish instant
    # every hunter shares, mirroring the meter's results-screen freeze.
    last = session.execute(
        select(func.max(DpsSnapshot.ts_offset_seconds))
        .where(DpsSnapshot.hunt_id == hunt_id)
    ).scalar()
    hunt = session.get(Hunt, hunt_id)
    return _hunt_wide_window(first, last, death, hunt, window)


def player_engagement_s(session: Session, hunt_id: int,
                        player_id: int,
                        window: str | None = None) -> float | None:
    """Active window for one hunter: own first->last damage snapshot.

    Handles mid-fight (SOS) joins, where the party-wide window would
    misattribute DPS: a late joiner's damage must be divided by their own
    time in the fight, not by first-hit->death. Falls back to the
    hunt-wide window when the hunter has fewer than two snapshots.

    ``window="quest"`` ends at the party's last hit instead (quest end,
    shared by the whole party), matching the in-game HunterPie meter.
    ``None`` follows the ``dps_window`` setting."""
    window = window or configured_dps_window()
    first, last = session.execute(
        select(func.min(DpsSnapshot.ts_offset_seconds),
               func.max(DpsSnapshot.ts_offset_seconds))
        .where(DpsSnapshot.hunt_id == hunt_id,
               DpsSnapshot.player_id == player_id)
    ).one()
    if window == DPS_WINDOW_QUEST and first is not None:
        quest_end = session.execute(
            select(func.max(DpsSnapshot.ts_offset_seconds))
            .where(DpsSnapshot.hunt_id == hunt_id)
        ).scalar()
        if quest_end is not None and quest_end > first:
            return quest_end - first
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

    3 GROUP BY queries total regardless of pair count: per-(hunt,player)
    snapshot min/max, per-hunt snapshot min/max, per-hunt monster-death
    (max HP step, engagement fallback only). Hunt-duration fallbacks come
    from the already-loaded Hunt objects — no extra query. Semantics match
    player_engagement_s exactly.

    ``window="quest"`` ends every window at the party's last hit (quest
    end, shared by the whole party). ``None`` follows the ``dps_window``
    setting."""
    window = window or configured_dps_window()
    if not pairs or not hunts_by_id:
        return {}
    ids = list(hunts_by_id.keys())
    deaths: dict[int, float] = {
        hid: mx
        for hid, mx in session.execute(
            select(MonsterHealthStep.hunt_id,
                   func.max(MonsterHealthStep.ts_offset_seconds))
            .where(MonsterHealthStep.hunt_id.in_(ids))
            .group_by(MonsterHealthStep.hunt_id)
        ).all()
    }
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
    out: dict[tuple[int, int], float | None] = {}
    for hid, pid in set(pairs):
        hunt = hunts_by_id.get(hid)
        h_first, h_last = snap.get(hid, (None, None))
        mn_mx = pp.get((hid, pid))
        if mn_mx is not None:
            first, last = mn_mx
            if window == DPS_WINDOW_QUEST:
                # Shared quest end: everyone divides by the same finish
                # instant from their own start. Matches the overlay, which
                # divides each hunter's damage by (results - own first).
                if (first is not None and h_last is not None
                        and h_last > first):
                    out[(hid, pid)] = h_last - first
                    continue
            if first is not None and last is not None and last > first:
                out[(hid, pid)] = last - first
                continue
        # hunt-wide fallback (mirrors engagement_duration_s)
        death = deaths.get(hid)
        out[(hid, pid)] = _hunt_wide_window(
            h_first, h_last, death, hunt, window)
    return out
