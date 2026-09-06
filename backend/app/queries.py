"""Dashboard query layer — one function per metric.

Adding a metric = add one function here returning JSON-serializable dicts,
then expose it with one route in api.py. No other files change.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import DpsSnapshot, Hunt, HuntPlayer, Monster, MonsterEvent, Player, Weapon


def _hunt_duration_s(hunt: Hunt) -> float | None:
    for candidate in (hunt.quest_time_seconds, hunt.real_hunt_time_seconds):
        if candidate:
            return float(candidate)
    if hunt.started_at and hunt.ended_at:
        return (hunt.ended_at - hunt.started_at).total_seconds() or None
    return None


def filter_options(session: Session) -> dict:
    """Dropdown options for dashboard filters (ids + names)."""
    return {
        "monsters": [{"id": m.id, "name": m.name} for m in session.execute(
            select(Monster).order_by(Monster.name)).scalars()],
        "weapons": [{"id": w.id, "name": w.name} for w in session.execute(
            select(Weapon).order_by(Weapon.name)).scalars()],
        "players": [{"id": p.id, "name": p.display_name} for p in session.execute(
            select(Player).order_by(Player.display_name)).scalars()],
    }


def health(session: Session) -> dict:
    hunts = session.execute(select(func.count(Hunt.id))).scalar_one()
    return {"status": "ok", "hunts": hunts}


def hunt_list(session: Session, limit: int = 200) -> dict:
    rows = session.execute(
        select(Hunt, Monster).join(Monster).order_by(Hunt.started_at.desc()).limit(limit)
    ).all()
    return {"hunts": [
        {"id": h.id, "monster": m.name, "started_at": h.started_at.isoformat(),
         "clear_s": _hunt_duration_s(h), "cleared": bool(h.cleared),
         "carts": h.cart_count, "players": h.player_count}
        for h, m in rows
    ]}


def progress(session: Session, monster_id: int | None = None,
             weapon_id: int | None = None, player_id: int | None = None,
             window: int = 5) -> dict:
    """FR-3.1: per-hunt DPS + clear time series with rolling average."""
    stmt = (
        select(Hunt, HuntPlayer, Player, Weapon, Monster)
        .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
        .join(Player, Player.id == HuntPlayer.player_id)
        .outerjoin(Weapon, Weapon.id == HuntPlayer.weapon_id)
        .join(Monster, Monster.id == Hunt.monster_id)
        .where(HuntPlayer.is_supporter.is_(False))
        .order_by(Hunt.started_at)
    )
    if monster_id is not None:
        stmt = stmt.where(Hunt.monster_id == monster_id)
    if weapon_id is not None:
        stmt = stmt.where(HuntPlayer.weapon_id == weapon_id)
    if player_id is not None:
        stmt = stmt.where(HuntPlayer.player_id == player_id)

    points = []
    for hunt, hp, player, weapon, monster in session.execute(stmt):
        dur = _hunt_duration_s(hunt)
        points.append({
            "hunt_id": hunt.id,
            "started_at": hunt.started_at.isoformat(),
            "monster": monster.name,
            "weapon": weapon.name if weapon else "Unknown",
            "player": player.display_name,
            "dps": (hp.total_damage / dur) if dur else 0.0,
            "clear_s": dur,
            "cleared": bool(hunt.cleared),
        })
    dps_vals = [p["dps"] for p in points]
    rolling = [
        {"hunt_id": p["hunt_id"],
         "avg_dps": sum(dps_vals[max(0, i - window + 1):i + 1])
         / len(dps_vals[max(0, i - window + 1):i + 1])}
        for i, p in enumerate(points)
    ]
    return {"points": points, "rolling": rolling, "window": window}


def weapon_matrix(session: Session) -> dict:
    """FR-3.2: per-weapon aggregates (supporters excluded)."""
    stmt = (
        select(Weapon.name, HuntPlayer.weapon_id, Hunt, HuntPlayer)
        .join(HuntPlayer, HuntPlayer.weapon_id == Weapon.id)
        .join(Hunt, Hunt.id == HuntPlayer.hunt_id)
        .where(HuntPlayer.is_supporter.is_(False))
    )
    by_weapon: dict[str, dict] = {}
    for name, _wid, hunt, hp in session.execute(stmt):
        dur = _hunt_duration_s(hunt)
        agg = by_weapon.setdefault(name, {"hunts": set(), "dps": [], "peak": 0.0,
                                          "clears": set()})
        agg["hunts"].add(hunt.id)
        if dur:
            agg["dps"].append(hp.total_damage / dur)
        agg["peak"] = max(agg["peak"], hp.peak_dps)
        if hunt.cleared:
            agg["clears"].add(hunt.id)
    # hunts played with no recorded weapon
    unknown_hunts = session.execute(
        select(func.count(func.distinct(HuntPlayer.hunt_id)))
        .where(HuntPlayer.weapon_id.is_(None),
               HuntPlayer.is_supporter.is_(False))
    ).scalar_one()
    rows = [{
        "weapon": name,
        "hunts": len(a["hunts"]),
        "avg_dps": sum(a["dps"]) / len(a["dps"]) if a["dps"] else 0.0,
        "peak_dps": a["peak"],
        "clear_rate": len(a["clears"]) / len(a["hunts"]) if a["hunts"] else 0.0,
    } for name, a in sorted(by_weapon.items())]
    if unknown_hunts:
        rows.append({"weapon": "Unknown", "hunts": unknown_hunts,
                     "avg_dps": 0.0, "peak_dps": 0.0, "clear_rate": 0.0})
    return {"weapons": rows}


def hunt_curve(session: Session, hunt_id: int, max_points: int = 500) -> dict:
    """FR-3.3: per-player cumulative damage series + monster event spans."""
    hunt = session.get(Hunt, hunt_id)
    if hunt is None:
        raise KeyError(hunt_id)
    snaps = session.execute(
        select(DpsSnapshot, Player.display_name)
        .join(Player, Player.id == DpsSnapshot.player_id)
        .where(DpsSnapshot.hunt_id == hunt_id)
        .order_by(DpsSnapshot.player_id, DpsSnapshot.ts_offset_seconds)
    ).all()
    # weapon per player comes from hunt_players, not the snapshot join above
    weapons = dict(session.execute(
        select(HuntPlayer.player_id, Weapon.name)
        .outerjoin(Weapon, Weapon.id == HuntPlayer.weapon_id)
        .where(HuntPlayer.hunt_id == hunt_id)
    ).all())
    series: dict[int, dict] = {}
    for snap, name in snaps:
        s = series.setdefault(snap.player_id,
                              {"player": name, "weapon": weapons.get(snap.player_id),
                               "points": []})
        s["points"].append({"t": snap.ts_offset_seconds, "dmg": snap.cumulative_damage})
    for s in series.values():
        pts = s["points"]
        if len(pts) > max_points:
            stride = len(pts) / max_points
            s["points"] = [pts[int(i * stride)] for i in range(max_points)]
            s["points"].append(pts[-1])
    events = session.execute(
        select(MonsterEvent).where(MonsterEvent.hunt_id == hunt_id)
        .order_by(MonsterEvent.start_offset_seconds)
    ).scalars().all()
    return {
        "hunt_id": hunt.id,
        "monster": hunt.monster.name,
        "started_at": hunt.started_at.isoformat(),
        "clear_s": _hunt_duration_s(hunt),
        "players": list(series.values()),
        "events": [{"type": e.event_type, "start": e.start_offset_seconds,
                    "end": e.end_offset_seconds} for e in events],
    }


def synergy(session: Session) -> dict:
    """FR-3.4: aggregate stats keyed by non-supporter teammate pairing."""
    stmt = (
        select(Hunt, Player.display_name, HuntPlayer.total_damage)
        .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
        .join(Player, Player.id == HuntPlayer.player_id)
        .where(HuntPlayer.is_supporter.is_(False))
        .order_by(Hunt.started_at)
    )
    hunts: dict[int, dict] = {}
    for hunt, name, dmg in session.execute(stmt):
        h = hunts.setdefault(hunt.id, {"hunt": hunt, "members": []})
        h["members"].append((name, dmg))
    pairings: dict[str, dict] = {}
    for h in hunts.values():
        key = " + ".join(sorted(n for n, _ in h["members"]))
        total = sum(d for _, d in h["members"]) or 1.0
        agg = pairings.setdefault(key, {"hunts": 0, "clears": 0, "clear_ss": [],
                                        "shares": {}})
        agg["hunts"] += 1
        if h["hunt"].cleared:
            agg["clears"] += 1
        dur = _hunt_duration_s(h["hunt"])
        if dur:
            agg["clear_ss"].append(dur)
        for name, dmg in h["members"]:
            agg["shares"].setdefault(name, []).append(dmg / total)
    rows = [{
        "pairing": key,
        "hunts": a["hunts"],
        "clear_rate": a["clears"] / a["hunts"],
        "avg_clear_s": (sum(a["clear_ss"]) / len(a["clear_ss"])
                        if a["clear_ss"] else None),
        "avg_share": {n: sum(v) / len(v) for n, v in a["shares"].items()},
    } for key, a in sorted(pairings.items(), key=lambda kv: -kv[1]["hunts"])]
    return {"pairings": rows}
