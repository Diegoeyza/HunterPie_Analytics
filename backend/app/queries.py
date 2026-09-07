"""Dashboard query layer — one function per metric.

Adding a metric = add one function here returning JSON-serializable dicts,
then expose it with one route in api.py. No other files change.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    DpsSnapshot,
    Hunt,
    HuntPlayer,
    Monster,
    MonsterEvent,
    MonsterHealthStep,
    Player,
    PlayerAbnormality,
    PlayerPin,
    Weapon,
    WeaponIdentity,
)


def _parse_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    return [int(x) for x in raw.split(",") if x.strip().isdigit()]


UNKNOWN_VARIANT_ID = 0
"""Pseudo variant id for hunts with no gear data (pre-gear fork exports)."""


def _variant_hunt_ids(session: Session, player_id: int,
                      variant_id: int) -> set[int]:
    """Hunt ids where ``player_id`` fought with the given weapon variant.

    ``variant_id`` is a WeaponIdentity id, or UNKNOWN_VARIANT_ID for hunts
    with NULL gear columns. Unknown identity ids yield the empty set.
    """
    stmt = select(HuntPlayer.hunt_id).where(HuntPlayer.player_id == player_id)
    if variant_id == UNKNOWN_VARIANT_ID:
        stmt = stmt.where(HuntPlayer.gear_raw.is_(None))
    else:
        identity = session.get(WeaponIdentity, variant_id)
        if identity is None:
            return set()
        stmt = stmt.where(
            HuntPlayer.gear_raw == identity.gear_raw,
            HuntPlayer.gear_element == identity.gear_element,
            HuntPlayer.gear_affinity == identity.gear_affinity,
        )
    return set(session.execute(stmt).scalars())


def _resolve_variant_filter(session: Session,
                            player_ids: list[int] | None,
                            variant_id: int | None) -> set[int] | None:
    """Shared variant narrowing for scoped queries.

    Only applies with exactly one scoped hunter (the dashboard only offers
    the filter then); otherwise returns None = no narrowing.
    """
    if variant_id is None or not player_ids or len(player_ids) != 1:
        return None
    return _variant_hunt_ids(session, player_ids[0], variant_id)


def _identity_label_map(session: Session) -> dict[tuple, str | None]:
    """(weapon_type, raw, element, affinity) -> user label (or None)."""
    return {(i.weapon_type, i.gear_raw, i.gear_element, i.gear_affinity): i.label
            for i in session.execute(select(WeaponIdentity)).scalars()}


def _gear_variant_label(label_map: dict[tuple, str | None], weapon_name: str | None,
                        raw: float | None, element: float | None,
                        affinity: float | None) -> str | None:
    if raw is None:
        return None
    return label_map.get((weapon_name or "Unknown", raw, element, affinity))


def player_variants(session: Session, player_id: int) -> dict:
    """Distinct gear fingerprints used by one hunter, with hunt counts."""
    rows = session.execute(
        select(Weapon.name, HuntPlayer.gear_raw, HuntPlayer.gear_element,
               HuntPlayer.gear_affinity,
               func.count(func.distinct(HuntPlayer.hunt_id)))
        .outerjoin(Weapon, Weapon.id == HuntPlayer.weapon_id)
        .where(HuntPlayer.player_id == player_id,
               HuntPlayer.gear_raw.is_not(None))
        .group_by(Weapon.name, HuntPlayer.gear_raw, HuntPlayer.gear_element,
                  HuntPlayer.gear_affinity)
    ).all()
    identities = {(i.weapon_type, i.gear_raw, i.gear_element, i.gear_affinity): i
                  for i in session.execute(select(WeaponIdentity)).scalars()}
    variants = []
    for wname, raw, element, affinity, hunts in rows:
        identity = identities.get((wname or "Unknown", raw, element, affinity))
        variants.append({
            "id": identity.id if identity else None,
            "weapon_type": wname or "Unknown",
            "raw": raw, "element": element, "affinity": affinity,
            "label": identity.label if identity else None,
            "hunts": hunts,
        })
    unknown = session.execute(
        select(func.count(func.distinct(HuntPlayer.hunt_id)))
        .where(HuntPlayer.player_id == player_id,
               HuntPlayer.gear_raw.is_(None))
    ).scalar_one()
    return {"player_id": player_id, "variants": variants, "unknown_hunts": unknown}


def set_identity_label(session: Session, identity_id: int,
                       label: str | None) -> dict:
    """Name (or un-name, with null/empty) a weapon variant. Label-once."""
    identity = session.get(WeaponIdentity, identity_id)
    if identity is None:
        raise KeyError(identity_id)
    identity.label = (label or "").strip() or None
    session.commit()
    return {"id": identity.id, "label": identity.label}


def _hunt_duration_s(hunt: Hunt) -> float | None:
    for candidate in (hunt.quest_time_seconds, hunt.real_hunt_time_seconds):
        if candidate:
            return float(candidate)
    if hunt.started_at and hunt.ended_at:
        return (hunt.ended_at - hunt.started_at).total_seconds() or None
    return None


def _engagement_duration_s(session: Session, hunt_id: int) -> float | None:
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
    return _hunt_duration_s(session.get(Hunt, hunt_id))


def _player_engagement_s(session: Session, hunt_id: int,
                          player_id: int) -> float | None:
    """Active window for one hunter: own first→last damage snapshot.

    Handles mid-fight (SOS) joins, where the party-wide window would
    misattribute DPS: a late joiner's damage must be divided by their own
    time in the fight, not by first-hit→death. Falls back to the
    hunt-wide window when the hunter has fewer than two snapshots."""
    first, last = session.execute(
        select(func.min(DpsSnapshot.ts_offset_seconds),
               func.max(DpsSnapshot.ts_offset_seconds))
        .where(DpsSnapshot.hunt_id == hunt_id,
               DpsSnapshot.player_id == player_id)
    ).one()
    if first is not None and last is not None and last > first:
        return last - first
    return _engagement_duration_s(session, hunt_id)


def filter_options(session: Session) -> dict:
    """Dropdown options for dashboard filters (ids + names)."""
    quests = session.execute(
        select(Hunt.quest_id, Monster.name, Hunt.monster_id, Hunt.quest_stars)
        .join(Monster, Monster.id == Hunt.monster_id)
        .where(Hunt.quest_id.is_not(None))
        .group_by(Hunt.quest_id, Monster.name, Hunt.monster_id, Hunt.quest_stars)
        .order_by(Hunt.quest_id)
    ).all()
    stars = session.execute(
        select(Hunt.quest_stars).where(Hunt.quest_stars.is_not(None))
        .group_by(Hunt.quest_stars).order_by(Hunt.quest_stars)
    ).scalars().all()
    monster_stars_rows = session.execute(
        select(Hunt.monster_id, Hunt.quest_stars)
        .where(Hunt.quest_stars.is_not(None))
        .group_by(Hunt.monster_id, Hunt.quest_stars)
        .order_by(Hunt.monster_id, Hunt.quest_stars)
    ).all()
    monster_stars: dict[int, list[int]] = {}
    for mid, s in monster_stars_rows:
        monster_stars.setdefault(mid, []).append(s)
    return {
        "monsters": [{"id": m.id, "name": m.name} for m in session.execute(
            select(Monster).order_by(Monster.name)).scalars()],
        "weapons": [{"id": w.id, "name": w.name} for w in session.execute(
            select(Weapon).order_by(Weapon.name)).scalars()],
        "players": [{"id": p.id, "name": p.display_name} for p in session.execute(
            select(Player).order_by(Player.display_name)).scalars()],
        "quests": [{"quest_id": q, "monster": m, "monster_id": mid, "stars": s}
                   for q, m, mid, s in quests],
        "stars": list(stars),
        "monster_stars": monster_stars,
    }


def list_pins(session: Session) -> dict:
    rows = session.execute(
        select(PlayerPin, Player.display_name)
        .join(Player, Player.id == PlayerPin.player_id)
        .order_by(Player.display_name)
    ).all()
    return {"pins": [{"player_id": pin.player_id, "name": name,
                      "pinned_at": pin.pinned_at.isoformat()} for pin, name in rows]}


def set_pin(session: Session, player_id: int, pinned: bool) -> dict:
    from datetime import datetime

    player = session.get(Player, player_id)
    if player is None:
        raise KeyError(player_id)
    existing = session.get(PlayerPin, player_id)
    if pinned and existing is None:
        session.add(PlayerPin(player_id=player_id, pinned_at=datetime.utcnow()))
        session.commit()
    elif not pinned and existing is not None:
        session.delete(existing)
        session.commit()
    return {"player_id": player_id, "pinned": pinned}


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
             quest_id: int | None = None, stars: int | None = None,
             player_ids: list[int] | None = None,
             window: int = 5, variant_id: int | None = None) -> dict:
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
    if quest_id is not None:
        stmt = stmt.where(Hunt.quest_id == quest_id)
    if stars is not None:
        stmt = stmt.where(Hunt.quest_stars == stars)
    if player_ids:
        stmt = stmt.where(HuntPlayer.player_id.in_(player_ids))
    variant_hunts = _resolve_variant_filter(session, player_ids, variant_id)
    if variant_hunts is not None:
        stmt = stmt.where(Hunt.id.in_(variant_hunts))

    labels = _identity_label_map(session)
    points = []
    for hunt, hp, player, weapon, monster in session.execute(stmt):
        dur = _player_engagement_s(session, hunt.id, hp.player_id)
        points.append({
            "hunt_id": hunt.id,
            "started_at": hunt.started_at.isoformat(),
            "monster": monster.name,
            "quest_id": hunt.quest_id,
            "quest_stars": hunt.quest_stars,
            "monster_max_hp": hunt.monster_max_hp,
            "weapon": weapon.name if weapon else "Unknown",
            "variant": _gear_variant_label(
                labels, weapon.name if weapon else None,
                hp.gear_raw, hp.gear_element, hp.gear_affinity),
            "player": player.display_name,
            "dps": (hp.total_damage / dur) if dur else 0.0,
            "clear_s": _hunt_duration_s(hunt),
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


def weapon_matrix(session: Session, player_ids: list[int] | None = None,
                   monster_id: int | None = None, stars: int | None = None,
                   variant_id: int | None = None) -> dict:
    """FR-3.2: per-weapon aggregates (supporters excluded)."""
    stmt = (
        select(Weapon.name, HuntPlayer.weapon_id, Hunt, HuntPlayer)
        .join(HuntPlayer, HuntPlayer.weapon_id == Weapon.id)
        .join(Hunt, Hunt.id == HuntPlayer.hunt_id)
        .where(HuntPlayer.is_supporter.is_(False))
    )
    if player_ids:
        stmt = stmt.where(HuntPlayer.player_id.in_(player_ids))
    if monster_id is not None:
        stmt = stmt.where(Hunt.monster_id == monster_id)
    if stars is not None:
        stmt = stmt.where(Hunt.quest_stars == stars)
    variant_hunts = _resolve_variant_filter(session, player_ids, variant_id)
    if variant_hunts is not None:
        stmt = stmt.where(Hunt.id.in_(variant_hunts))
    by_weapon: dict[str, dict] = {}
    for name, _wid, hunt, hp in session.execute(stmt):
        dur = _player_engagement_s(session, hunt.id, hp.player_id)
        agg = by_weapon.setdefault(name, {"hunts": set(), "dps": [], "peak": 0.0,
                                           "clears": set()})
        agg["hunts"].add(hunt.id)
        if dur:
            agg["dps"].append(hp.total_damage / dur)
        agg["peak"] = max(agg["peak"], hp.peak_dps)
        if hunt.cleared:
            agg["clears"].add(hunt.id)
    # hunts played with no recorded weapon
    unk_stmt = (
        select(func.count(func.distinct(HuntPlayer.hunt_id)))
        .join(Hunt, Hunt.id == HuntPlayer.hunt_id)
        .where(HuntPlayer.weapon_id.is_(None),
               HuntPlayer.is_supporter.is_(False))
    )
    if monster_id is not None:
        unk_stmt = unk_stmt.where(Hunt.monster_id == monster_id)
    if stars is not None:
        unk_stmt = unk_stmt.where(Hunt.quest_stars == stars)
    unknown_hunts = session.execute(unk_stmt).scalar_one()
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


def hunt_curve(session: Session, hunt_id: int, max_points: int = 500,
               quest_hp: bool = False) -> dict:
    """FR-3.3: per-player cumulative damage series + monster event spans.

    quest_hp=True also returns the HP steps of every sibling hunt from the
    same quest (same started_at), so multi-monster quests can draw all
    monsters' HP on one chart. Snapshots are identical across siblings
    (full quest damage each); only HP steps and events differ per monster.
    """
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
    hp_rows = session.execute(
        select(HuntPlayer.player_id, Weapon.name, HuntPlayer.gear_raw,
               HuntPlayer.gear_element, HuntPlayer.gear_affinity)
        .outerjoin(Weapon, Weapon.id == HuntPlayer.weapon_id)
        .where(HuntPlayer.hunt_id == hunt_id)
    ).all()
    labels = _identity_label_map(session)
    weapons: dict[int, dict] = {}
    for pid, wname, raw, element, affinity in hp_rows:
        weapons[pid] = {
            "name": wname,
            "variant": _gear_variant_label(labels, wname, raw, element,
                                           affinity),
        }
    series: dict[int, dict] = {}
    for snap, name in snaps:
        w = weapons.get(snap.player_id, {})
        s = series.setdefault(snap.player_id,
                              {"player": name, "weapon": w.get("name"),
                               "variant": w.get("variant"),
                               "points": []})
        s["points"].append({"t": snap.ts_offset_seconds, "dmg": snap.cumulative_damage,
                            "dps": snap.instant_dps})
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
    hp = session.execute(
        select(MonsterHealthStep).where(MonsterHealthStep.hunt_id == hunt_id)
        .order_by(MonsterHealthStep.ts_offset_seconds)
    ).scalars().all()
    out = {
        "hunt_id": hunt.id,
        "monster": hunt.monster.name,
        "started_at": hunt.started_at.isoformat(),
        "clear_s": _hunt_duration_s(hunt),
        "quest": {"quest_id": hunt.quest_id, "stars": hunt.quest_stars,
                  "level": hunt.quest_level, "max_hp": hunt.monster_max_hp,
                  "variant": hunt.monster_variant, "crown": hunt.monster_crown},
        "players": list(series.values()),
        "events": [{"type": e.event_type, "start": e.start_offset_seconds,
                    "end": e.end_offset_seconds} for e in events],
        "hp_curve": [{"t": s.ts_offset_seconds, "hp": s.hp_fraction} for s in hp],
    }
    if quest_hp:
        siblings = session.execute(
            select(Hunt).where(Hunt.started_at == hunt.started_at)
            .order_by(Hunt.id)
        ).scalars().all()
        quest_curves = []
        for sib in siblings:
            steps = session.execute(
                select(MonsterHealthStep)
                .where(MonsterHealthStep.hunt_id == sib.id)
                .order_by(MonsterHealthStep.ts_offset_seconds)
            ).scalars().all()
            quest_curves.append({
                "hunt_id": sib.id, "monster": sib.monster.name,
                "points": [{"t": s.ts_offset_seconds, "hp": s.hp_fraction}
                           for s in steps],
            })
        out["quest_hp"] = quest_curves
    return out


def hunt_abnormalities(session: Session, hunt_id: int) -> dict:
    """Abnormality activations for a hunt, grouped by player."""
    from .abnormality_names import get_abnormality_name
    hunt = session.get(Hunt, hunt_id)
    if hunt is None:
        raise KeyError(hunt_id)
    rows = session.execute(
        select(PlayerAbnormality, Player.display_name)
        .join(Player, Player.id == PlayerAbnormality.player_id)
        .where(PlayerAbnormality.hunt_id == hunt_id)
        .order_by(Player.display_name, PlayerAbnormality.abnormality_id,
                  PlayerAbnormality.started_at_offset)
    ).all()
    players: dict[str, dict] = {}
    for ab, pname in rows:
        pa = players.setdefault(pname, {"player": pname, "abnormalities": []})
        pa["abnormalities"].append({
            "id": ab.abnormality_id,
            "name": get_abnormality_name(ab.abnormality_id),
            "category": ab.category,
            "start": ab.started_at_offset,
            "end": ab.finished_at_offset,
        })
    return {
        "hunt_id": hunt_id,
        "monster": hunt.monster.name,
        "started_at": hunt.started_at.isoformat(),
        "clear_s": _hunt_duration_s(hunt),
        "players": list(players.values()),
    }


def synergy(session: Session, player_ids: list[int] | None = None,
            monster_id: int | None = None, stars: int | None = None,
            variant_id: int | None = None) -> dict:
    """FR-3.4: aggregate stats keyed by non-supporter teammate pairing.

    player_ids narrows to hunts including ALL of those hunters."""
    stmt = (
        select(Hunt, Player.display_name, HuntPlayer.total_damage, HuntPlayer.player_id)
        .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
        .join(Player, Player.id == HuntPlayer.player_id)
        .where(HuntPlayer.is_supporter.is_(False))
        .order_by(Hunt.started_at)
    )
    if monster_id is not None:
        stmt = stmt.where(Hunt.monster_id == monster_id)
    if stars is not None:
        stmt = stmt.where(Hunt.quest_stars == stars)
    hunts: dict[int, dict] = {}
    for hunt, name, dmg, pid in session.execute(stmt):
        h = hunts.setdefault(hunt.id, {"hunt": hunt, "members": []})
        h["members"].append((name, dmg, pid))
    if player_ids:
        want = set(player_ids)
        hunts = {hid: h for hid, h in hunts.items()
                 if want <= {pid for _, _, pid in h["members"]}}
    variant_hunts = _resolve_variant_filter(session, player_ids, variant_id)
    if variant_hunts is not None:
        hunts = {hid: h for hid, h in hunts.items() if hid in variant_hunts}
    pairings: dict[str, dict] = {}
    for h in hunts.values():
        key = " + ".join(sorted(n for n, _, _ in h["members"]))
        total = sum(d for _, d, _ in h["members"]) or 1.0
        agg = pairings.setdefault(key, {"hunts": 0, "clears": 0, "clear_ss": [],
                                        "shares": {}})
        agg["hunts"] += 1
        if h["hunt"].cleared:
            agg["clears"] += 1
        dur = _hunt_duration_s(h["hunt"])
        if dur:
            agg["clear_ss"].append(dur)
        for name, dmg, _ in h["members"]:
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


def quest_stats(session: Session) -> dict:
    """Per-quest aggregates: same monster, different HP per quest id."""
    hunts = session.execute(
        select(Hunt, Monster.name)
        .join(Monster, Monster.id == Hunt.monster_id)
        .order_by(Hunt.quest_id, Hunt.started_at)
    ).all()
    by_quest: dict[int, dict] = {}
    for hunt, monster_name in hunts:
        qid = hunt.quest_id if hunt.quest_id is not None else -hunt.id
        agg = by_quest.setdefault(qid, {
            "quest_id": hunt.quest_id, "monster": monster_name,
            "stars": hunt.quest_stars, "max_hp": hunt.monster_max_hp,
            "hunts": 0, "clears": 0, "clear_ss": [], "best": None,
            "best_dps": 0.0, "carts": 0})
        agg["hunts"] += 1
        agg["carts"] += hunt.cart_count
        if hunt.monster_max_hp:
            agg["max_hp"] = max(agg["max_hp"] or 0, hunt.monster_max_hp)
        dur = _hunt_duration_s(hunt)
        if hunt.cleared:
            agg["clears"] += 1
        if dur:
            agg["clear_ss"].append(dur)
            if hunt.cleared and (agg["best"] is None or dur < agg["best"][1]):
                agg["best"] = (hunt.id, dur)
    for qid, agg in by_quest.items():
        id_filter = (Hunt.quest_id == qid) if qid > 0 else (Hunt.id == -qid)
        for dmg, pid, hunt in session.execute(
            select(HuntPlayer.total_damage, HuntPlayer.player_id, Hunt)
            .join(Hunt, Hunt.id == HuntPlayer.hunt_id)
            .where(id_filter, HuntPlayer.is_supporter.is_(False))
        ).all():
            eng = _player_engagement_s(session, hunt.id, pid)
            if eng:
                agg["best_dps"] = max(agg["best_dps"], (dmg or 0.0) / eng)
        spans = session.execute(
            select(MonsterEvent.start_offset_seconds,
                   MonsterEvent.end_offset_seconds, MonsterEvent.hunt_id)
            .join(Hunt, Hunt.id == MonsterEvent.hunt_id)
            .where(id_filter, MonsterEvent.event_type == "enrage")
        ).all()
        total_span = sum((e - s) for s, e, _ in spans if s is not None and e is not None)
        agg["enrage_uptime"] = (total_span / sum(agg["clear_ss"])) if agg["clear_ss"] else 0.0
    rows = [{
        "quest_id": a["quest_id"], "monster": a["monster"], "stars": a["stars"],
        "max_hp": a["max_hp"], "hunts": a["hunts"], "carts": a["carts"],
        "clear_rate": a["clears"] / a["hunts"] if a["hunts"] else 0.0,
        "avg_clear_s": (sum(a["clear_ss"]) / len(a["clear_ss"]) if a["clear_ss"] else None),
        "best_clear": ({"hunt_id": a["best"][0], "clear_s": a["best"][1]}
                       if a["best"] else None),
        "best_dps": a["best_dps"],
        "enrage_uptime": a["enrage_uptime"],
    } for a in sorted(by_quest.values(),
                      key=lambda a: (a["quest_id"] is None, a["quest_id"] or 0))]
    return {"quests": rows}


def records(session: Session) -> dict:
    """Personal bests per monster: fastest clear + highest single-hunt DPS."""
    rows = session.execute(
        select(Hunt, HuntPlayer, Player.display_name, Weapon.name, Monster.name)
        .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
        .join(Player, Player.id == HuntPlayer.player_id)
        .outerjoin(Weapon, Weapon.id == HuntPlayer.weapon_id)
        .join(Monster, Monster.id == Hunt.monster_id)
        .where(HuntPlayer.is_supporter.is_(False))
    ).all()
    by_monster: dict[str, dict] = {}
    for hunt, hp, pname, wname, mname in rows:
        dur = _hunt_duration_s(hunt)
        eng = _player_engagement_s(session, hunt.id, hp.player_id)
        dps = ((hp.total_damage or 0.0) / eng) if eng else 0.0
        agg = by_monster.setdefault(mname, {"hunts": set(), "fastest": None,
                                            "top_dps": None})
        agg["hunts"].add(hunt.id)
        if hunt.cleared and dur and (agg["fastest"] is None or dur < agg["fastest"]["clear_s"]):
            members = sorted({n for h2, _, n, _, m2 in rows
                              if h2.id == hunt.id and m2 == mname})
            agg["fastest"] = {"hunt_id": hunt.id, "clear_s": dur,
                              "date": hunt.started_at.date().isoformat(),
                              "party": members, "carts": hunt.cart_count}
        if agg["top_dps"] is None or dps > agg["top_dps"]["dps"]:
            agg["top_dps"] = {"hunt_id": hunt.id, "player": pname,
                              "weapon": wname or "Unknown", "dps": dps,
                              "date": hunt.started_at.date().isoformat()}
    return {"records": [{
        "monster": m, "hunts": len(a["hunts"]),
        "fastest": a["fastest"], "top_dps": a["top_dps"],
    } for m, a in sorted(by_monster.items())]}


def high_scores(session: Session, player_ids: list[int] | None = None,
                monster_id: int | None = None, weapon_id: int | None = None,
                stars: int | None = None, sort_by: str = "dps",
                limit: int | None = None,
                variant_id: int | None = None) -> dict:
    """Cleared-hunt leaderboard: one row per hunt, ranked.

    ``player_ids`` (global hunter scope) narrows to hunts including ANY of
    those hunters; the featured DPS is the best among the scoped members
    present (or the party top DPS when no scope). ``weapon_id`` applies to
    the featured player. ``variant_id`` (with exactly one scoped hunter)
    narrows to hunts where that hunter used the weapon variant.
    ``sort_by`` is ``"dps"`` (highest featured DPS first) or ``"time"``
    (fastest clear first). ``limit`` keeps only the top N rows (client
    Top-N filter).
    """
    sort_by = "time" if sort_by == "time" else "dps"
    stmt = (
        select(Hunt, HuntPlayer, Player.display_name, Weapon.name, Weapon.id,
               Monster.name)
        .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
        .join(Player, Player.id == HuntPlayer.player_id)
        .outerjoin(Weapon, Weapon.id == HuntPlayer.weapon_id)
        .join(Monster, Monster.id == Hunt.monster_id)
        .where(Hunt.cleared.is_(True), HuntPlayer.is_supporter.is_(False))
    )
    if monster_id is not None:
        stmt = stmt.where(Hunt.monster_id == monster_id)
    if stars is not None:
        stmt = stmt.where(Hunt.quest_stars == stars)

    labels = _identity_label_map(session)
    by_hunt: dict[int, dict] = {}
    for hunt, hp, pname, wname, wid, mname in session.execute(stmt):
        eng = _player_engagement_s(session, hunt.id, hp.player_id)
        h = by_hunt.setdefault(hunt.id, {"hunt": hunt, "monster": mname,
                                         "members": []})
        h["members"].append({
            "player_id": hp.player_id,
            "player": pname,
            "weapon": wname or "Unknown",
            "weapon_id": wid,
            "variant": _gear_variant_label(
                labels, wname, hp.gear_raw, hp.gear_element, hp.gear_affinity),
            "dps": ((hp.total_damage or 0.0) / eng) if eng else 0.0,
        })

    variant_hunts = _resolve_variant_filter(session, player_ids, variant_id)
    scores: list[dict] = []
    for h in by_hunt.values():
        if variant_hunts is not None and h["hunt"].id not in variant_hunts:
            continue
        members = h["members"]
        if player_ids and not any(m["player_id"] in player_ids for m in members):
            continue
        pool = ([m for m in members if m["player_id"] in player_ids]
                if player_ids else members)
        featured = max(pool, key=lambda m: (m["dps"], m["player"]))
        if weapon_id is not None and featured["weapon_id"] != weapon_id:
            continue
        clear_s = _hunt_duration_s(h["hunt"])
        party = sorted((m for m in members if m["player"] != featured["player"]),
                       key=lambda m: (-m["dps"], m["player"]))
        scores.append({
            "hunt_id": h["hunt"].id,
            "date": h["hunt"].started_at.date().isoformat(),
            "monster": h["monster"],
            "stars": h["hunt"].quest_stars,
            "clear_s": clear_s,
            "player": featured["player"],
            "weapon": featured["weapon"],
            "variant": featured["variant"],
            "dps": featured["dps"],
            "party": [{"player": m["player"], "weapon": m["weapon"],
                       "variant": m["variant"],
                       "dps": m["dps"]} for m in party],
        })
    if sort_by == "dps":
        scores.sort(key=lambda s: (-s["dps"], s["hunt_id"]))
    else:
        scores.sort(key=lambda s: (s["clear_s"] is None,
                                   s["clear_s"] if s["clear_s"] is not None
                                   else float("inf"),
                                   s["hunt_id"]))
    if limit is not None and limit > 0:
        scores = scores[:limit]
    for rank, s in enumerate(scores, 1):
        s["rank"] = rank
    return {"scores": scores}


def activity(session: Session) -> dict:
    """Hunts per day + clear rate + avg DPS (heatmap fuel)."""
    rows = session.execute(
        select(Hunt, HuntPlayer.total_damage, HuntPlayer.player_id)
        .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
        .where(HuntPlayer.is_supporter.is_(False))
    ).all()
    by_day: dict[str, dict] = {}
    for hunt, dmg, pid in rows:
        day = hunt.started_at.date().isoformat()
        agg = by_day.setdefault(day, {"hunts": set(), "clears": set(),
                                      "dps": [], "damage": 0.0})
        agg["hunts"].add(hunt.id)
        if hunt.cleared:
            agg["clears"].add(hunt.id)
        agg["damage"] += dmg or 0.0
        dur = _player_engagement_s(session, hunt.id, pid)
        if dur:
            agg["dps"].append((dmg or 0.0) / dur)
    return {"days": [{
        "date": d, "hunts": len(a["hunts"]),
        "clear_rate": len(a["clears"]) / len(a["hunts"]) if a["hunts"] else 0.0,
        "avg_dps": sum(a["dps"]) / len(a["dps"]) if a["dps"] else 0.0,
        "total_damage": a["damage"],
    } for d, a in sorted(by_day.items())]}


def compare(session: Session, player_ids: list[int], window: int = 5,
              variant_id: int | None = None) -> dict:
    """Scoped hunters' DPS vs whole-party DPS per hunt (needs a scope)."""
    if not player_ids:
        return {"points": [], "window": window, "scope": []}
    want = set(player_ids)
    rows = session.execute(
        select(Hunt, HuntPlayer)
        .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
        .where(HuntPlayer.is_supporter.is_(False))
        .order_by(Hunt.started_at)
    ).all()
    hunts: dict[int, dict] = {}
    for hunt, hp in rows:
        h = hunts.setdefault(hunt.id, {"hunt": hunt, "all": [], "scope": []})
        dur = _player_engagement_s(session, hunt.id, hp.player_id)
        dps = ((hp.total_damage or 0.0) / dur) if dur else 0.0
        h["all"].append(dps)
        if hp.player_id in want:
            h["scope"].append(dps)
    variant_hunts = _resolve_variant_filter(session, player_ids, variant_id)
    if variant_hunts is not None:
        hunts = {hid: h for hid, h in hunts.items() if hid in variant_hunts}
    points = [{
        "hunt_id": hid,
        "date": h["hunt"].started_at.date().isoformat(),
        "scope_dps": sum(h["scope"]) / len(h["scope"]),
        "party_dps": sum(h["all"]) / len(h["all"]),
    } for hid, h in hunts.items() if h["scope"]]
    for key in ("scope_dps", "party_dps"):
        vals = [p[key] for p in points]
        for i, p in enumerate(points):
            seg = vals[max(0, i - window + 1):i + 1]
            p[f"avg_{key}"] = sum(seg) / len(seg)
    names = session.execute(
        select(Player.display_name).where(Player.id.in_(player_ids))
    ).scalars().all()
    return {"points": points, "window": window, "scope": sorted(names)}
