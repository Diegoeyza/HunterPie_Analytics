"""Dashboard query layer — one function per metric.

Adding a metric = add one function here returning JSON-serializable dicts,
then expose it with one route in api.py. No other files change.
"""
from __future__ import annotations

import json
from datetime import UTC

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import filters
from .abnormalities import EXCLUDED_STORED_IDS, AbnormalityId
from .engagement import (
    batch_capped_damage_s,
    batch_engagement_s,
    hunt_duration_s,
)
from .filters import FilterError, parse_ids
from .models import (
    Award,
    DpsSnapshot,
    Hunt,
    HuntPlayer,
    HuntPlayerAward,
    Monster,
    MonsterEvent,
    MonsterHealthStep,
    Player,
    PlayerAbnormality,
    PlayerAlias,
    PlayerHealthStep,
    PlayerPin,
    Weapon,
)
from .variants import (
    UNKNOWN_VARIANT_ID,
    gear_variant_label,
    identity_label_map,
    player_variants,
    resolve_variant_filter,
    set_identity_label,
)
from .version import bundled_mod_version, version_lt

# Backward-compat aliases (old private names still importable).
_parse_ids = parse_ids
_visible = filters.visible
_party = filters.party
_hunt_duration_s = hunt_duration_s
_batch_engagement_s = batch_engagement_s


def _dps_windows(session, hunts_by_id, pairs):
    """Engagement windows + quest-frozen damage totals in one go.

    ``cap`` maps (hunt, player) -> damage as of the quest freeze point in
    quest mode ({} in engagement mode): divide it — not total_damage — by
    the window, so post-freeze ticks count for neither side. Callers keep
    ``cap.get(key, total)`` so fallback pairs still use the full total.
    """
    return (batch_engagement_s(session, hunts_by_id, pairs),
            batch_capped_damage_s(session, hunts_by_id, pairs))
_resolve_variant_filter = resolve_variant_filter
_identity_label_map = identity_label_map
_gear_variant_label = gear_variant_label

# Preferred display order for the 30 quest awards, by game id (0..29). The
# "active play" awards hunters watch come first; the rest keep their id order.
_AWARD_PRIORITY = [0, 24, 29, 4, 3, 18, 28, 16]
_AWARD_RANK = {aid: rank for rank, aid in enumerate(_AWARD_PRIORITY)}


def _award_sort_key(aid: int) -> tuple[int, int]:
    """Sort awards: priority list first (in that order), then by id."""
    return (_AWARD_RANK.get(aid, len(_AWARD_PRIORITY)), aid)


__all__ = [
    "FilterError",
    "UNKNOWN_VARIANT_ID",
    "parse_ids",
    "set_hunt_ignored",
    "player_variants",
    "set_identity_label",
    "filter_options",
    "list_pins",
    "set_pin",
    "health",
    "hunt_list",
    "progress",
    "weapon_matrix",
    "hunt_curve",
    "hunt_abnormalities",
    "synergy",
    "quest_stats",
    "quest_hunts",
    "records",
    "high_scores",
    "leaderboard",
    "activity",
    "compare",
    "progress_improvement",
    "list_aliases",
    "dismiss_alias",
    "merge_alias",
]


def set_hunt_ignored(session: Session, hunt_id: int, ignored: bool) -> dict:
    """Hide (or restore) a hunt from every stat view. Reversible."""
    hunt = session.get(Hunt, hunt_id)
    if hunt is None:
        raise KeyError(hunt_id)
    hunt.ignored = bool(ignored)
    session.commit()
    return {"id": hunt.id, "ignored": bool(hunt.ignored)}




def filter_options(session: Session) -> dict:
    """Dropdown options for dashboard filters (ids + names).

    One row per quest_id: multi-monster quests list every target in
    `monster` ("Arkveld + Gore Magala") instead of one row per
    (quest, monster) which duplicated option values downstream."""
    quest_rows = session.execute(
        select(Hunt.quest_id, Monster.name, Hunt.monster_id, Hunt.quest_stars)
        .join(Monster, Monster.id == Hunt.monster_id)
        .where(Hunt.quest_id.is_not(None), filters.visible())
        .order_by(Hunt.quest_id, Hunt.started_at)
    ).all()
    quests: list[dict] = []
    by_quest: dict[tuple, dict] = {}
    for q, m, mid, s in quest_rows:
        # Unknown stars (e.g. field surveys) reuse quest slots across
        # targets: split those by monster so unrelated hunts don't merge.
        key = (q,) if s is not None else (q, mid)
        agg = by_quest.get(key)
        if agg is None:
            agg = by_quest[key] = {"quest_id": q, "monsters": [],
                                   "monster_id": mid, "stars": s}
            quests.append(agg)
        if m not in agg["monsters"]:
            agg["monsters"].append(m)
    stars = session.execute(
        select(Hunt.quest_stars).where(Hunt.quest_stars.is_not(None), filters.visible())
        .group_by(Hunt.quest_stars).order_by(Hunt.quest_stars)
    ).scalars().all()
    monster_stars_rows = session.execute(
        select(Hunt.monster_id, Hunt.quest_stars)
        .where(Hunt.quest_stars.is_not(None), filters.visible())
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
        "awards": [{"id": a.id, "name": a.name, "explain": a.explain,
                    "unit": a.unit}
                   for a in sorted(
            session.execute(select(Award)).scalars(),
            key=lambda a: _award_sort_key(a.id))],
        "players": [{"id": p.id, "name": p.display_name} for p in session.execute(
            select(Player).order_by(Player.display_name)).scalars()],
        "quests": [{"quest_id": q["quest_id"],
                    "monster": " + ".join(q["monsters"]),
                    "monster_id": q["monster_id"], "stars": q["stars"]}
                   for q in quests],
        "stars": list(stars),
        "monster_stars": monster_stars,
    }


def player_weapon_names(session: Session, player_id: int) -> dict:
    """Distinct weapon names a hunter used, with hunt counts.

    Names come from the REFramework mod's LOCAL-player lookup, so only that
    player has them. Powers the hunter-scoped weapon-name filter."""
    rows = session.execute(
        select(HuntPlayer.weapon_name,
               func.count(func.distinct(HuntPlayer.hunt_id)))
        .join(Hunt, Hunt.id == HuntPlayer.hunt_id)
        .where(HuntPlayer.player_id == player_id,
               HuntPlayer.weapon_name.is_not(None), filters.visible())
        .group_by(HuntPlayer.weapon_name)
        .order_by(func.count(func.distinct(HuntPlayer.hunt_id)).desc(),
                  HuntPlayer.weapon_name)
    ).all()
    unknown = session.execute(
        select(func.count(func.distinct(HuntPlayer.hunt_id)))
        .join(Hunt, Hunt.id == HuntPlayer.hunt_id)
        .where(HuntPlayer.player_id == player_id,
               HuntPlayer.weapon_name.is_(None), filters.visible())
    ).scalar_one()
    return {"weapons": [{"name": n, "hunts": c} for n, c in rows],
            "unknown_hunts": unknown}


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
        session.add(PlayerPin(player_id=player_id, pinned_at=datetime.now(UTC).replace(tzinfo=None)))
        session.commit()
    elif not pinned and existing is not None:
        session.delete(existing)
        session.commit()
    return {"player_id": player_id, "pinned": pinned}


def health(session: Session) -> dict:
    hunts = session.execute(
        select(func.count(Hunt.id)).where(filters.visible())).scalar_one()
    latest = session.execute(
        select(Hunt.hunterpie_version, Hunt.game_version)
        .where(filters.visible())
        .order_by(Hunt.started_at.desc()).limit(1)
    ).one_or_none()
    out = {"status": "ok", "hunts": hunts}
    if latest is not None:
        out["hunterpie_version"], out["game_version"] = latest
    return out


def mod_status(session: Session) -> dict:
    """Newest HuntDumper version seen in a dump vs. the one bundled here.

    ``installed`` is the version from the most recent hunt that carried a
    mod_version (companion-only hunts are ignored: NULL). ``outdated`` drives
    the dashboard's "reinstall the mod" toast after an app update."""
    expected = bundled_mod_version()
    installed = session.execute(
        select(Hunt.mod_version)
        .where(Hunt.mod_version.is_not(None))
        .order_by(Hunt.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return {"expected": expected, "installed": installed,
            "outdated": version_lt(installed, expected)}


def hunt_list(session: Session, limit: int = 200,
              include_ignored: bool = False,
              player_ids: list[int] | None = None,
              party: int | None = None,
              weapon_name: str | None = None,
              source: str | None = None) -> dict:
    stmt = select(Hunt, Monster).join(Monster)
    if not include_ignored:
        stmt = stmt.where(filters.visible())
    if player_ids:
        stmt = (stmt.join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
                .where(HuntPlayer.player_id.in_(player_ids))
                .distinct())
    elif weapon_name is not None:
        stmt = stmt.join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id).distinct()
    if weapon_name is not None:
        stmt = stmt.where(HuntPlayer.weapon_name == weapon_name)
    if source is not None:
        stmt = stmt.where(Hunt.source == source)
    stmt = filters.party(stmt, party)
    rows = session.execute(
        stmt.order_by(Hunt.started_at.desc()).limit(limit)
    ).all()
    hunt_ids = [h.id for h, _m in rows]
    highlights = _hunt_highlight_summary(session, hunt_ids)
    with_buffs = set(session.execute(
        select(PlayerAbnormality.hunt_id)
        .join(Hunt, Hunt.id == PlayerAbnormality.hunt_id)
        .where(PlayerAbnormality.hunt_id.in_(hunt_ids))
        # Buffs are companion-only: legacy rows on hunts the mod created are
        # stale, and buildup meters are gauges rather than windows.
        .where(Hunt.source == "hunterpie")
        .where(PlayerAbnormality.abnormality_id.notin_(EXCLUDED_STORED_IDS))
        .distinct()
    ).scalars()) if hunt_ids else set()
    with_health = set(session.execute(
        select(PlayerHealthStep.hunt_id)
        .where(PlayerHealthStep.hunt_id.in_(hunt_ids))
        .distinct()
    ).scalars()) if hunt_ids else set()
    return {"hunts": [
        {"id": h.id, "monster": m.name, "started_at": h.started_at.isoformat(),
         "quest_id": h.quest_id, "quest_stars": h.quest_stars,
         "clear_s": hunt_duration_s(h), "cleared": bool(h.cleared),
         "carts": h.cart_count, "players": h.player_count,
         "ignored": bool(h.ignored),
         "source": h.source,
         "has_buffs": h.id in with_buffs,
         "has_health": h.id in with_health,
         "highlight_count": highlights.get(h.id, {}).get("count", 0),
         "highlight_names": highlights.get(h.id, {}).get("names", [])}
        for h, m in rows
    ]}


def _hunt_highlight_summary(session: Session, hunt_ids: list[int],
                            max_names: int = 8) -> dict[int, dict]:
    """Per-hunt count + top award names scored by anyone (damage excluded:
    award id 4 is shared by every player and is not a distinguishing
    highlight). Non-zero counts only; not all hunts have awards (fork)."""
    if not hunt_ids:
        return {}
    rows = session.execute(
        select(HuntPlayerAward.hunt_id, HuntPlayerAward.award_id,
               HuntPlayerAward.count, Award.name)
        .join(Award, Award.id == HuntPlayerAward.award_id)
        .where(HuntPlayerAward.hunt_id.in_(hunt_ids),
               HuntPlayerAward.award_id != 4,
               HuntPlayerAward.count > 0)
    ).all()
    best: dict[int, dict[int, tuple[float, str]]] = {}
    for hid, aid, count, name in rows:
        cur = best.setdefault(hid, {}).get(aid)
        if cur is None or count > cur[0]:
            best[hid][aid] = (count, name)
    out: dict[int, dict] = {}
    for hid, by_award in best.items():
        ranked = sorted(by_award.values(), key=lambda t: (-t[0], t[1]))
        out[hid] = {"count": len(by_award),
                    "names": [n for _c, n in ranked[:max_names]]}
    return out


def progress(session: Session, monster_id: int | None = None,
             weapon_id: int | None = None, player_id: int | None = None,
             quest_id: int | None = None, stars: int | None = None,
             player_ids: list[int] | None = None,
             window: int = 5, variant_id: int | str | None = None,
             limit: int | None = None, party: int | None = None,
             weapon_name: str | None = None,
             include_failed: bool = False) -> dict:
    """FR-3.1: per-hunt DPS + clear time series with rolling average.

    ``limit`` keeps only the most recent N hunts (by started_at); None =
    all. Hunt-level filters (monster/quest/stars) apply to the hunt
    selection so e.g. limit=100 with a monster filter = last 100 hunts of
    that monster."""
    if limit is not None and limit > 0:
        hq = (select(Hunt.id)
              .where(filters.visible(), filters.cleared(include_failed))
              .order_by(Hunt.started_at.desc()).limit(limit))
        if monster_id is not None:
            hq = hq.where(Hunt.monster_id == monster_id)
        if quest_id is not None:
            hq = hq.where(Hunt.quest_id == quest_id)
        if stars is not None:
            hq = hq.where(Hunt.quest_stars == stars)
        hq = filters.party(hq, party)
        recent = set(session.execute(hq).scalars())
        if not recent:
            return {"points": [], "rolling": [], "window": window}
    else:
        recent = None
    stmt = (
        select(Hunt, HuntPlayer, Player, Weapon, Monster)
        .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
        .join(Player, Player.id == HuntPlayer.player_id)
        .outerjoin(Weapon, Weapon.id == HuntPlayer.weapon_id)
        .join(Monster, Monster.id == Hunt.monster_id)
        .where(HuntPlayer.is_supporter.is_(False), filters.visible(),
               filters.cleared(include_failed))
        .order_by(Hunt.started_at)
    )
    if recent is not None:
        stmt = stmt.where(Hunt.id.in_(recent))
    if monster_id is not None:
        stmt = stmt.where(Hunt.monster_id == monster_id)
    if weapon_id is not None:
        stmt = stmt.where(HuntPlayer.weapon_id == weapon_id)
    if weapon_name is not None:
        stmt = stmt.where(HuntPlayer.weapon_name == weapon_name)
    if player_id is not None:
        stmt = stmt.where(HuntPlayer.player_id == player_id)
    if quest_id is not None:
        stmt = stmt.where(Hunt.quest_id == quest_id)
    if stars is not None:
        stmt = stmt.where(Hunt.quest_stars == stars)
    if player_ids:
        stmt = stmt.where(HuntPlayer.player_id.in_(player_ids))
    stmt = filters.party(stmt, party)
    variant_hunts = resolve_variant_filter(session, player_ids, variant_id)
    if variant_hunts is not None:
        stmt = stmt.where(Hunt.id.in_(variant_hunts))

    labels = identity_label_map(session)
    rows = list(session.execute(stmt))
    hunts_by_id = {h.id: h for h, _hp, _p, _w, _m in rows}
    eng, cap = _dps_windows(
        session, hunts_by_id,
        [(h.id, hp.player_id) for h, hp, _p, _w, _m in rows])
    points = []
    for hunt, hp, player, weapon, monster in rows:
        dur = eng.get((hunt.id, hp.player_id))
        points.append({
            "hunt_id": hunt.id,
            "started_at": hunt.started_at.isoformat(),
            "monster": monster.name,
            "quest_id": hunt.quest_id,
            "quest_stars": hunt.quest_stars,
            "monster_max_hp": hunt.monster_max_hp,
            "weapon": weapon.name if weapon else "Unknown",
            "variant": gear_variant_label(
                labels, weapon.name if weapon else None,
                hp.gear_raw, hp.gear_element, hp.gear_affinity),
            "player": player.display_name,
            "dps": (cap.get((hunt.id, hp.player_id), hp.total_damage) / dur) if dur else 0.0,
            "clear_s": hunt_duration_s(hunt),
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
                   variant_id: int | str | None = None,
                   party: int | None = None,
                   weapon_name: str | None = None,
                   include_failed: bool = False) -> dict:
    """FR-3.2: per-weapon aggregates (supporters excluded).

    Avg/peak DPS come from the performance pool (cleared hunts only unless
    ``include_failed``); the hunt count and clear rate span every attempt so
    the clear rate still reflects failures."""
    stmt = (
        select(Weapon.name, HuntPlayer.weapon_id, Hunt, HuntPlayer)
        .join(HuntPlayer, HuntPlayer.weapon_id == Weapon.id)
        .join(Hunt, Hunt.id == HuntPlayer.hunt_id)
        .where(HuntPlayer.is_supporter.is_(False), filters.visible())
    )
    stmt = filters.party(stmt, party)
    if player_ids:
        stmt = stmt.where(HuntPlayer.player_id.in_(player_ids))
    if monster_id is not None:
        stmt = stmt.where(Hunt.monster_id == monster_id)
    if stars is not None:
        stmt = stmt.where(Hunt.quest_stars == stars)
    if weapon_name is not None:
        stmt = stmt.where(HuntPlayer.weapon_name == weapon_name)
    variant_hunts = resolve_variant_filter(session, player_ids, variant_id)
    if variant_hunts is not None:
        stmt = stmt.where(Hunt.id.in_(variant_hunts))
    rows = list(session.execute(stmt))
    hunts_by_id = {h.id: h for _n, _w, h, _hp in rows}
    eng, cap = _dps_windows(
        session, hunts_by_id, [(h.id, hp.player_id) for _n, _w, h, hp in rows])
    by_weapon: dict[str, dict] = {}
    for name, _wid, hunt, hp in rows:
        dur = eng.get((hunt.id, hp.player_id))
        agg = by_weapon.setdefault(name, {"hunts": set(), "dps": [], "peak": 0.0,
                                           "clears": set()})
        agg["hunts"].add(hunt.id)
        eligible = include_failed or bool(hunt.cleared)
        if dur and eligible:
            agg["dps"].append(cap.get((hunt.id, hp.player_id), hp.total_damage) / dur)
        if eligible:
            agg["peak"] = max(agg["peak"], hp.peak_dps)
        if hunt.cleared:
            agg["clears"].add(hunt.id)
    # hunts played with no recorded weapon
    unk_stmt = (
        select(func.count(func.distinct(HuntPlayer.hunt_id)))
        .join(Hunt, Hunt.id == HuntPlayer.hunt_id)
        .where(HuntPlayer.weapon_id.is_(None),
               HuntPlayer.is_supporter.is_(False), filters.visible())
    )
    if monster_id is not None:
        unk_stmt = unk_stmt.where(Hunt.monster_id == monster_id)
    if stars is not None:
        unk_stmt = unk_stmt.where(Hunt.quest_stars == stars)
    unk_stmt = filters.party(unk_stmt, party)
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


# Longest gap that still counts toward time-in-danger. The mod emits a
# heartbeat every 5 s, so a normal gap is <=5 s; anything longer is a loading
# screen/alt-tab (or a capture hole) and must be skipped, not counted.
_SURVIVAL_MAX_GAP = 6.0


def _survival_stats(points: list[tuple[float, float]]) -> dict:
    """Time-weighted survival summary for sorted [(t, hp_fraction)] samples."""
    if not points:
        return {"min_hp": None, "avg_hp": None, "time_below_50": 0.0,
                "time_below_25": 0.0, "time_full": 0.0,
                "samples": 0}
    total = 0.0
    weighted = 0.0
    below_50 = 0.0
    below_25 = 0.0
    full = 0.0
    for (t0, hp0), (t1, _hp1) in zip(points, points[1:], strict=False):
        dt = t1 - t0
        if dt <= 0 or dt > _SURVIVAL_MAX_GAP:
            continue
        total += dt
        weighted += hp0 * dt
        if hp0 < 0.5:
            below_50 += dt
        if hp0 < 0.25:
            below_25 += dt
        if hp0 >= 0.995:
            full += dt
    hps = [hp for _t, hp in points]
    avg = (weighted / total) if total > 0 else (sum(hps) / len(hps))
    return {"min_hp": min(hps), "avg_hp": avg, "time_below_50": below_50,
            "time_below_25": below_25, "time_full": full,
            "samples": len(points)}


def _anchor_dps_origin(points: list[dict]) -> None:
    """Start a damage series at quest time 0.

    Companion exports begin at the first hit, so the cumulative-damage curve
    would otherwise begin partway across the Survival chart while hunter HP
    begins at 0. Prepending (0, 0) is factual when no damage was recorded
    before that sample. A late-attached companion is different: its first
    sample carries all the damage already dealt (bulk value), so anchoring it
    at 0 would invent a flat "no damage" stretch. Skip those.
    """
    if len(points) < 2:
        return
    first, last = points[0], points[-1]
    if first["t"] <= 0:
        return
    if last["dmg"] > 0 and first["dmg"] > 0.25 * last["dmg"]:
        return
    points.insert(0, {"t": 0.0, "dmg": 0.0, "dps": 0.0})


def hunt_curve(session: Session, hunt_id: int, max_points: int = 500,
               quest_hp: bool = False) -> dict:
    """FR-3.3: per-player cumulative damage series + monster event spans.

    quest_hp=True also returns the HP steps of every sibling hunt from the
    same quest (quest_id_external or started_at match), so
    multi-monster quests can draw all monsters' HP on one chart, plus the
    enrage/abnormality spans of every sibling hunt (any number of
    monsters). Snapshots are identical across siblings (full quest damage
    each); only HP steps and events differ per monster.
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
    labels = identity_label_map(session)
    weapons: dict[int, dict] = {}
    for pid, wname, raw, element, affinity in hp_rows:
        weapons[pid] = {
            "name": wname,
            "variant": gear_variant_label(labels, wname, raw, element,
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
        _anchor_dps_origin(s["points"])
    hp = session.execute(
        select(MonsterHealthStep).where(MonsterHealthStep.hunt_id == hunt_id)
        .order_by(MonsterHealthStep.ts_offset_seconds)
    ).scalars().all()
    # Per-player HP samples (REFramework mod only; empty for companion hunts).
    # Player HP is quest-wide, so a sibling of a multi-monster quest (e.g. a
    # monster the mod skipped as a bystander) borrows it: siblings share
    # started_at, so their offsets line up exactly.
    php_hunt_ids = [hunt_id]
    has_own_hp = session.execute(
        select(func.count()).select_from(PlayerHealthStep)
        .where(PlayerHealthStep.hunt_id == hunt_id)).scalar_one()
    if not has_own_hp:
        php_hunt_ids += session.execute(
            select(PlayerHealthStep.hunt_id)
            .join(Hunt, Hunt.id == PlayerHealthStep.hunt_id)
            .where(Hunt.started_at == hunt.started_at,
                   Hunt.id != hunt_id)
            .limit(1)).scalars().all()
    php_rows = session.execute(
        select(Player.display_name, PlayerHealthStep)
        .join(Player, Player.id == PlayerHealthStep.player_id)
        .where(PlayerHealthStep.hunt_id.in_(php_hunt_ids))
        .order_by(Player.display_name, PlayerHealthStep.ts_offset_seconds)
    ).all()
    player_hp: list[dict] = []
    survival: list[dict] = []
    grouped: dict[str, list] = {}
    for name, row in php_rows:
        grouped.setdefault(name, []).append(row)
    for name, rows in grouped.items():
        pts = [{"t": r.ts_offset_seconds, "hp": r.hp_fraction,
                "red": r.red_fraction, "max": r.max_hp} for r in rows]
        if len(pts) > max_points:
            stride = len(pts) / max_points
            pts = [pts[int(i * stride)] for i in range(max_points)]
            pts.append({"t": rows[-1].ts_offset_seconds,
                        "hp": rows[-1].hp_fraction,
                        "red": rows[-1].red_fraction,
                        "max": rows[-1].max_hp})
        player_hp.append({"player": name, "points": pts})
        stats = _survival_stats([(r.ts_offset_seconds, r.hp_fraction)
                                 for r in rows])
        stats["player"] = name
        survival.append(stats)
    # Sibling hunts = all (visible) hunts from the same quest instance:
    # same started_at (microsecond precision, identical for every monster
    # row imported from one file). quest_id_external must NOT be used here:
    # it is a per-SESSION hash shared by every quest of a gaming session, so
    # matching on it merges unrelated same-monster quests (e.g. three
    # back-to-back Arkvelds) into one chart. One row per monster, any
    # number. Resolved once so both quest_hp curves and quest-wide events
    # use the same set.
    sib_stmt = select(Hunt).where(filters.visible())
    sib_stmt = sib_stmt.where(Hunt.started_at == hunt.started_at)
    siblings = session.execute(
        sib_stmt.order_by(Hunt.id)).scalars().all()
    if not siblings:
        siblings = [hunt]
    sibling_ids = [s.id for s in siblings]
    sibling_monster = {s.id: s.monster.name for s in siblings}
    own_name = sibling_monster.get(hunt.id, hunt.monster.name)

    def _event_dict(hunt_id_val: int, monster_name: str | None,
                    e: MonsterEvent) -> dict:
        return {"type": e.event_type, "start": e.start_offset_seconds,
                "end": e.end_offset_seconds, "monster": monster_name,
                "hunt_id": hunt_id_val}

    if quest_hp:
        quest_events = session.execute(
            select(MonsterEvent, Monster.name)
            .join(Monster, Monster.id == MonsterEvent.monster_id)
            .where(MonsterEvent.hunt_id.in_(sibling_ids))
            .order_by(MonsterEvent.start_offset_seconds)
        ).all()
        events_out = [_event_dict(e.hunt_id, mname, e)
                      for e, mname in quest_events]
    else:
        own_events = session.execute(
            select(MonsterEvent).where(MonsterEvent.hunt_id == hunt_id)
            .order_by(MonsterEvent.start_offset_seconds)
        ).scalars().all()
        events_out = [_event_dict(hunt_id, own_name, e) for e in own_events]
    out = {
        "hunt_id": hunt.id,
        "monster": hunt.monster.name,
        "started_at": hunt.started_at.isoformat(),
        "clear_s": hunt_duration_s(hunt),
        "cleared": bool(hunt.cleared),
        "quest": {"quest_id": hunt.quest_id, "stars": hunt.quest_stars,
                  "level": hunt.quest_level, "max_hp": hunt.monster_max_hp,
                  "variant": hunt.monster_variant, "crown": hunt.monster_crown},
        "players": list(series.values()),
        "events": events_out,
        "hp_curve": [{"t": s.ts_offset_seconds, "hp": s.hp_fraction} for s in hp],
        "player_hp": player_hp,
        "survival": survival,
    }
    if quest_hp:
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
    hunt = session.get(Hunt, hunt_id)
    if hunt is None:
        raise KeyError(hunt_id)
    # Buffs are companion-only: a hunt only the mod captured has none, even if
    # a legacy import left rows behind.
    rows = [] if hunt.source != "hunterpie" else session.execute(
        select(PlayerAbnormality, Player.display_name)
        .join(Player, Player.id == PlayerAbnormality.player_id)
        .where(PlayerAbnormality.hunt_id == hunt_id)
        .order_by(Player.display_name, PlayerAbnormality.abnormality_id,
                  PlayerAbnormality.started_at_offset)
    ).all()
    players: dict[str, dict] = {}
    for ab, pname in rows:
        parsed = AbnormalityId.parse(ab.abnormality_id)
        if not parsed.is_displayable:
            continue
        pa = players.setdefault(pname, {"player": pname, "abnormalities": []})
        pa["abnormalities"].append({
            "id": ab.abnormality_id,
            "name": parsed.display_name,
            "category": parsed.group,
            "start": ab.started_at_offset,
            "end": ab.finished_at_offset,
        })
    return {
        "hunt_id": hunt_id,
        "monster": hunt.monster.name,
        "started_at": hunt.started_at.isoformat(),
        "clear_s": hunt_duration_s(hunt),
        "players": list(players.values()),
    }


def synergy(session: Session, player_ids: list[int] | None = None,
            monster_id: int | None = None, stars: int | None = None,
            variant_id: int | str | None = None,
            party: int | None = None,
            include_failed: bool = False) -> dict:
    """FR-3.4: aggregate stats keyed by non-supporter teammate pairing.

    player_ids narrows to hunts including ALL of those hunters. Hunt counts
    and clear rate span every attempt (failures included); damage shares come
    from the performance pool (cleared only unless ``include_failed``)."""
    stmt = (
        select(Hunt, Player.display_name, HuntPlayer.total_damage, HuntPlayer.player_id)
        .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
        .join(Player, Player.id == HuntPlayer.player_id)
        .where(HuntPlayer.is_supporter.is_(False), filters.visible())
        .order_by(Hunt.started_at)
    )
    if monster_id is not None:
        stmt = stmt.where(Hunt.monster_id == monster_id)
    if stars is not None:
        stmt = stmt.where(Hunt.quest_stars == stars)
    stmt = filters.party(stmt, party)
    if player_ids:
        # Hunts including ALL scoped hunters (was a Python post-filter over
        # the full table): hunt ids whose distinct scoped-member count
        # covers the whole scope.
        want = set(player_ids)
        stmt = stmt.where(Hunt.id.in_(
            select(HuntPlayer.hunt_id)
            .where(HuntPlayer.player_id.in_(want))
            .group_by(HuntPlayer.hunt_id)
            .having(func.count(func.distinct(HuntPlayer.player_id)) == len(want))
        ))
    hunts: dict[int, dict] = {}
    for hunt, name, dmg, pid in session.execute(stmt):
        h = hunts.setdefault(hunt.id, {"hunt": hunt, "members": []})
        h["members"].append((name, dmg, pid))
    variant_hunts = resolve_variant_filter(session, player_ids, variant_id)
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
        dur = hunt_duration_s(h["hunt"])
        if dur:
            agg["clear_ss"].append(dur)
        if include_failed or h["hunt"].cleared:
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


def quest_stats(session: Session, party: int | None = None) -> dict:
    """Per-quest aggregates: same monster, different HP per quest id."""
    hunts = session.execute(
        filters.party(
            select(Hunt, Monster.name)
            .join(Monster, Monster.id == Hunt.monster_id)
            .where(filters.visible())
            .order_by(Hunt.quest_id, Hunt.started_at),
            party)
    ).all()
    by_quest: dict[tuple, dict] = {}
    for hunt, monster_name in hunts:
        # Real quests group by quest_id. Unknown-star slots (e.g. field
        # surveys) reuse ids across targets, so split those by monster;
        # untracked hunts stay one row per hunt.
        if hunt.quest_id is None:
            key = ("hunt", hunt.id)
        elif hunt.quest_stars is None:
            key = ("survey", hunt.quest_id, hunt.monster_id)
        else:
            key = ("quest", hunt.quest_id)
        agg = by_quest.setdefault(key, {
            "key": (f"hunt:{hunt.id}" if key[0] == "hunt"
                    else f"survey:{key[1]}:{key[2]}" if key[0] == "survey"
                    else f"quest:{key[1]}"),
            "quest_id": hunt.quest_id, "monsters": [],
            "stars": hunt.quest_stars, "max_hp": hunt.monster_max_hp,
            "hunts": 0, "clears": 0, "clear_ss": [], "best": None,
            "best_dps": 0.0, "carts": 0})
        if monster_name not in agg["monsters"]:
            agg["monsters"].append(monster_name)
        agg["hunts"] += 1
        agg["carts"] += hunt.cart_count
        if hunt.monster_max_hp:
            agg["max_hp"] = max(agg["max_hp"] or 0, hunt.monster_max_hp)
        dur = hunt_duration_s(hunt)
        if hunt.cleared:
            agg["clears"] += 1
        if dur:
            agg["clear_ss"].append(dur)
            if hunt.cleared and (agg["best"] is None or dur < agg["best"][1]):
                agg["best"] = (hunt.id, dur)
    # Batched per-quest DPS + enrage (was 2 queries per quest group).
    hunt_key: dict[int, tuple] = {}
    for hunt, _mname in hunts:
        if hunt.quest_id is None:
            hunt_key[hunt.id] = ("hunt", hunt.id)
        elif hunt.quest_stars is None:
            hunt_key[hunt.id] = ("survey", hunt.quest_id, hunt.monster_id)
        else:
            hunt_key[hunt.id] = ("quest", hunt.quest_id)
    hunts_by_id = {h.id: h for h, _m in hunts}
    hp_stmt = (
        select(HuntPlayer.total_damage, HuntPlayer.player_id, HuntPlayer.hunt_id)
        .join(Hunt, Hunt.id == HuntPlayer.hunt_id)
        .where(HuntPlayer.is_supporter.is_(False), filters.visible())
    )
    hp_stmt = filters.party(hp_stmt, party)
    hp_rows = session.execute(hp_stmt).all()
    eng, cap = _dps_windows(
        session, hunts_by_id, [(hid, pid) for _d, pid, hid in hp_rows])
    for dmg, pid, hid in hp_rows:
        agg = by_quest.get(hunt_key.get(hid))
        if agg is None:
            continue
        e = eng.get((hid, pid))
        if e:
            agg["best_dps"] = max(agg["best_dps"], cap.get((hid, pid), dmg or 0.0) / e)
    enrage_stmt = (
        select(MonsterEvent.start_offset_seconds,
               MonsterEvent.end_offset_seconds, MonsterEvent.hunt_id)
        .join(Hunt, Hunt.id == MonsterEvent.hunt_id)
        .where(MonsterEvent.event_type == "enrage", filters.visible())
    )
    enrage_stmt = filters.party(enrage_stmt, party)
    enrage_rows = session.execute(enrage_stmt).all()
    enrage_by_key: dict[tuple, float] = {}
    for s, e, hid in enrage_rows:
        if s is None or e is None:
            continue
        key = hunt_key.get(hid)
        if key is None:
            continue
        enrage_by_key[key] = enrage_by_key.get(key, 0.0) + (e - s)
    for key, agg in by_quest.items():
        total_span = enrage_by_key.get(key, 0.0)
        agg["enrage_uptime"] = (total_span / sum(agg["clear_ss"])) if agg["clear_ss"] else 0.0
    rows = [{
        "key": a["key"],
        "quest_id": a["quest_id"], "monster": " + ".join(a["monsters"]), "stars": a["stars"],
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


def quest_hunts(session: Session, key: str,
                party: int | None = None) -> dict:
    """One quest-stats group as individual quest instances, for the popup.

    key mirrors quest_stats grouping: hunt:<id> (untracked), survey:<qid>:<mid>
    (starless slot split by monster), quest:<qid> (real quest, repeat runs).
    Each repeat run is its own instance with its hunters' damage + DPS
    (engagement divisor, same as best_dps), latest first. KeyError on a bad
    key or an empty (all-ignored) group.
    """
    parts = (key or "").split(":")
    kind = parts[0] if parts else ""
    try:
        if kind == "hunt" and len(parts) == 2:
            hunt_ids = [int(parts[1])]
        elif kind == "survey" and len(parts) == 3:
            qid, mid = int(parts[1]), int(parts[2])
            hunt_ids = [hid for (hid,) in session.execute(
                select(Hunt.id).where(filters.visible(), Hunt.quest_id == qid,
                                      Hunt.quest_stars.is_(None),
                                      Hunt.monster_id == mid)
            ).all()]
        elif kind == "quest" and len(parts) == 2:
            qid = int(parts[1])
            hunt_ids = [hid for (hid,) in session.execute(
                select(Hunt.id).where(filters.visible(), Hunt.quest_id == qid,
                                      Hunt.quest_stars.is_not(None))
            ).all()]
        else:
            raise ValueError(f"bad quest key: {key!r}")
    except (ValueError, IndexError):
        raise KeyError(key) from None
    if party is not None:
        hunt_ids = [hid for (hid,) in session.execute(
            select(Hunt.id).where(Hunt.id.in_(hunt_ids),
                                  Hunt.player_count == party)
        ).all()]
    if not hunt_ids:
        raise KeyError(key)

    hunts = session.execute(
        select(Hunt).where(Hunt.id.in_(hunt_ids))
        .order_by(Hunt.started_at.desc())
    ).scalars().all()
    rows = session.execute(
        select(HuntPlayer.hunt_id, HuntPlayer.player_id,
               Player.display_name, Weapon.name, HuntPlayer.total_damage)
        .join(Player, Player.id == HuntPlayer.player_id)
        .join(Weapon, Weapon.id == HuntPlayer.weapon_id, isouter=True)
        .where(HuntPlayer.hunt_id.in_(hunt_ids))
    ).all()
    hunts_by_id = {h.id: h for h in hunts}
    eng, cap = _dps_windows(
        session, hunts_by_id, [(hid, pid) for hid, pid, _n, _w, _d in rows])
    by_hunt: dict[int, list] = {}
    for hid, pid, name, weapon, damage in rows:
        dmg = damage or 0.0
        e = eng.get((hid, pid))
        by_hunt.setdefault(hid, []).append({
            "player": name, "weapon": weapon or "Unknown",
            "total_damage": dmg, "dps": (cap.get((hid, pid), dmg) / e) if e else None,
        })
    for members in by_hunt.values():
        members.sort(key=lambda m: m["total_damage"], reverse=True)
    return {"key": key, "hunts": [{
        "id": h.id, "started_at": h.started_at.isoformat(),
        "clear_s": hunt_duration_s(h), "cleared": bool(h.cleared),
        "carts": h.cart_count, "members": by_hunt.get(h.id, []),
    } for h in hunts]}


def records(session: Session, party: int | None = None) -> dict:
    """Personal bests per monster: fastest clear + highest single-hunt DPS."""
    rows = session.execute(
        filters.party(
            select(Hunt, HuntPlayer, Player.display_name, Weapon.name, Monster.name)
            .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
            .join(Player, Player.id == HuntPlayer.player_id)
            .outerjoin(Weapon, Weapon.id == HuntPlayer.weapon_id)
            .join(Monster, Monster.id == Hunt.monster_id)
            .where(HuntPlayer.is_supporter.is_(False), filters.visible()),
            party)
    ).all()
    by_monster: dict[str, dict] = {}
    hunts_by_id = {h.id: h for h, _hp, _n, _w, _m in rows}
    eng, cap = _dps_windows(
        session, hunts_by_id, [(h.id, hp.player_id) for h, hp, _n, _w, _m in rows])
    # Party members per hunt (single pass — was an O(n²) rescan per fastest).
    party_by_hunt: dict[int, set[str]] = {}
    for h, _hp, pname, _w, mname in rows:
        party_by_hunt.setdefault((h.id, mname), set()).add(pname)
    for hunt, hp, pname, wname, mname in rows:
        dur = hunt_duration_s(hunt)
        e = eng.get((hunt.id, hp.player_id))
        dps = (cap.get((hunt.id, hp.player_id), hp.total_damage or 0.0) / e) if e else 0.0
        agg = by_monster.setdefault(mname, {"hunts": set(), "fastest": None,
                                            "top_dps": None})
        agg["hunts"].add(hunt.id)
        if hunt.cleared and dur and (agg["fastest"] is None or dur < agg["fastest"]["clear_s"]):
            members = sorted(party_by_hunt.get((hunt.id, mname), set()))
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
                variant_id: int | str | None = None,
                include_ignored: bool = False,
                party: int | None = None,
                weapon_name: str | None = None,
                include_failed: bool = False) -> dict:
    """Cleared-hunt leaderboard: one row per hunt, ranked.

    ``player_ids`` (global hunter scope) narrows to hunts including ANY of
    those hunters; the featured DPS is the best among the scoped members
    present (or the party top DPS when no scope). ``weapon_id`` narrows the
    pool to members using that weapon first, so the featured row is the best
    weapon-user in the hunt (scoped or not). ``variant_id`` (with exactly one scoped hunter)
    narrows to hunts where that hunter used the weapon variant.
    ``sort_by`` is ``"dps"`` (highest featured DPS first) or ``"time"``
    (fastest clear first). ``limit`` keeps only the top N rows (client
    Top-N filter). Ignored hunts are excluded unless ``include_ignored``.
    """
    sort_by = "time" if sort_by == "time" else "dps"
    stmt = (
        select(Hunt, HuntPlayer, Player.display_name, Weapon.name, Weapon.id,
               Monster.name)
        .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
        .join(Player, Player.id == HuntPlayer.player_id)
        .outerjoin(Weapon, Weapon.id == HuntPlayer.weapon_id)
        .join(Monster, Monster.id == Hunt.monster_id)
        .where(filters.cleared(include_failed), HuntPlayer.is_supporter.is_(False))
    )
    if not include_ignored:
        stmt = stmt.where(filters.visible())
    if monster_id is not None:
        stmt = stmt.where(Hunt.monster_id == monster_id)
    if stars is not None:
        stmt = stmt.where(Hunt.quest_stars == stars)
    if weapon_name is not None:
        stmt = stmt.where(HuntPlayer.weapon_name == weapon_name)
    stmt = filters.party(stmt, party)

    labels = identity_label_map(session)
    stmt_rows = list(session.execute(stmt))
    hunts_by_id = {h.id: h for h, _hp, _n, _w, _wid, _m in stmt_rows}
    eng, cap = _dps_windows(
        session, hunts_by_id,
        [(h.id, hp.player_id) for h, hp, _n, _w, _wid, _m in stmt_rows])
    by_hunt: dict[int, dict] = {}
    for hunt, hp, pname, wname, wid, mname in stmt_rows:
        e = eng.get((hunt.id, hp.player_id))
        h = by_hunt.setdefault(hunt.id, {"hunt": hunt, "monster": mname,
                                         "members": []})
        h["members"].append({
            "player_id": hp.player_id,
            "player": pname,
            "weapon": wname or "Unknown",
            "weapon_id": wid,
            "variant": gear_variant_label(
                labels, wname, hp.gear_raw, hp.gear_element, hp.gear_affinity),
            "dps": (cap.get((hunt.id, hp.player_id), hp.total_damage or 0.0) / e) if e else 0.0,
        })

    variant_hunts = resolve_variant_filter(session, player_ids, variant_id)
    scores: list[dict] = []
    for h in by_hunt.values():
        if variant_hunts is not None and h["hunt"].id not in variant_hunts:
            continue
        members = h["members"]
        if player_ids and not any(m["player_id"] in player_ids for m in members):
            continue
        pool = ([m for m in members if m["player_id"] in player_ids]
                if player_ids else members)
        if weapon_id is not None:
            pool = [m for m in pool if m["weapon_id"] == weapon_id]
        if not pool:
            continue
        featured = max(pool, key=lambda m: (m["dps"], m["player"]))
        clear_s = hunt_duration_s(h["hunt"])
        rest = sorted((m for m in members if m["player"] != featured["player"]),
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
            "ignored": bool(h["hunt"].ignored),
            "party": [{"player": m["player"], "weapon": m["weapon"],
                       "variant": m["variant"],
                       "dps": m["dps"]} for m in rest],
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


def leaderboard(session: Session, player_ids: list[int] | None = None,
                monster_id: int | None = None, stars: int | None = None,
                weapon_id: int | None = None,
                variant_id: int | str | None = None,
                min_hunts: int = 1, party: int | None = None,
                weapon_name: str | None = None,
                include_failed: bool = False) -> dict:
    """Best-players ranking: per-hunter aggregates over cleared hunts.

    ``player_ids`` (global hunter scope): empty = rank everyone, otherwise
    rank only the scoped hunters. ``monster_id``/``stars`` narrow the hunt
    pool; ``weapon_id`` counts only rows where the hunter used that weapon.
    ``variant_id`` (with exactly one scoped hunter) narrows to hunts where
    that hunter used the weapon variant. ``min_hunts`` gates one-off
    performances (1 = no gate).
    """
    min_hunts = max(1, int(min_hunts or 1))
    stmt = (
        select(Hunt, HuntPlayer, Player.display_name)
        .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
        .join(Player, Player.id == HuntPlayer.player_id)
        .where(filters.cleared(include_failed), HuntPlayer.is_supporter.is_(False),
               filters.visible())
    )
    if monster_id is not None:
        stmt = stmt.where(Hunt.monster_id == monster_id)
    if stars is not None:
        stmt = stmt.where(Hunt.quest_stars == stars)
    if weapon_id is not None:
        stmt = stmt.where(HuntPlayer.weapon_id == weapon_id)
    if weapon_name is not None:
        stmt = stmt.where(HuntPlayer.weapon_name == weapon_name)
    stmt = filters.party(stmt, party)
    variant_hunts = resolve_variant_filter(session, player_ids, variant_id)
    if variant_hunts is not None:
        stmt = stmt.where(Hunt.id.in_(variant_hunts))
    rows = list(session.execute(stmt))
    hunts_by_id = {h.id: h for h, _hp, _n in rows}
    eng, cap = _dps_windows(
        session, hunts_by_id, [(h.id, hp.player_id) for h, hp, _n in rows])
    by_player: dict[int, dict] = {}
    for hunt, hp, pname in rows:
        agg = by_player.setdefault(hp.player_id, {
            "player_id": hp.player_id, "player": pname,
            "hunts": set(), "dps": [], "best": 0.0})
        agg["hunts"].add(hunt.id)
        e = eng.get((hunt.id, hp.player_id))
        dps = (cap.get((hunt.id, hp.player_id), hp.total_damage or 0.0) / e) if e else 0.0
        agg["dps"].append(dps)
        agg["best"] = max(agg["best"], dps)
    want = set(player_ids or [])
    leaders = [{
        "player_id": a["player_id"],
        "player": a["player"],
        "hunts": len(a["hunts"]),
        "avg_dps": sum(a["dps"]) / len(a["dps"]) if a["dps"] else 0.0,
        "best_dps": a["best"],
    } for a in by_player.values()
        if len(a["hunts"]) >= min_hunts and (not want or a["player_id"] in want)]
    leaders.sort(key=lambda r: (-r["avg_dps"], r["player"]))
    return {"leaders": leaders}


def activity(session: Session, party: int | None = None) -> dict:
    """Hunts per day + clear rate + avg DPS (heatmap fuel)."""
    rows = session.execute(
        filters.party(
            select(Hunt, HuntPlayer.total_damage, HuntPlayer.player_id)
            .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
            .where(HuntPlayer.is_supporter.is_(False), filters.visible())
            .order_by(Hunt.started_at),
            party)
    ).all()
    by_day: dict[str, dict] = {}
    hunts_by_id = {h.id: h for h, _d, _p in rows}
    eng, cap = _dps_windows(
        session, hunts_by_id, [(h.id, pid) for h, _d, pid in rows])
    for hunt, dmg, pid in rows:
        day = hunt.started_at.date().isoformat()
        agg = by_day.setdefault(day, {"hunts": set(), "clears": set(),
                                      "dps": [], "damage": 0.0})
        agg["hunts"].add(hunt.id)
        if hunt.cleared:
            agg["clears"].add(hunt.id)
        agg["damage"] += dmg or 0.0
        dur = eng.get((hunt.id, pid))
        if dur:
            agg["dps"].append(cap.get((hunt.id, pid), dmg or 0.0) / dur)
    return {"days": [{
        "date": d, "hunts": len(a["hunts"]),
        "clear_rate": len(a["clears"]) / len(a["hunts"]) if a["hunts"] else 0.0,
        "avg_dps": sum(a["dps"]) / len(a["dps"]) if a["dps"] else 0.0,
        "total_damage": a["damage"],
    } for d, a in sorted(by_day.items())]}


def compare(session: Session, player_ids: list[int], window: int = 5,
              variant_id: int | str | None = None,
              party: int | None = None,
              include_failed: bool = False) -> dict:
    """Scoped hunters' DPS vs whole-party DPS per hunt (needs a scope)."""
    if not player_ids:
        return {"points": [], "window": window, "scope": []}
    want = set(player_ids)
    stmt = (
        select(Hunt, HuntPlayer)
        .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
        .where(HuntPlayer.is_supporter.is_(False), filters.visible(),
               filters.cleared(include_failed))
        # Only hunts with at least one scoped member can contribute points.
        .where(Hunt.id.in_(
            select(HuntPlayer.hunt_id)
            .where(HuntPlayer.player_id.in_(want))
        ))
        .order_by(Hunt.started_at)
    )
    stmt = filters.party(stmt, party)
    rows = session.execute(stmt).all()
    hunts: dict[int, dict] = {}
    hunts_by_id = {h.id: h for h, _hp in rows}
    eng, cap = _dps_windows(
        session, hunts_by_id, [(h.id, hp.player_id) for h, hp in rows])
    for hunt, hp in rows:
        h = hunts.setdefault(hunt.id, {"hunt": hunt, "all": [], "scope": []})
        dur = eng.get((hunt.id, hp.player_id))
        dps = (cap.get((hunt.id, hp.player_id), hp.total_damage or 0.0) / dur) if dur else 0.0
        h["all"].append(dps)
        if hp.player_id in want:
            h["scope"].append(dps)
    variant_hunts = resolve_variant_filter(session, player_ids, variant_id)
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


def hunt_highlights(session: Session, hunt_id: int) -> dict:
    """Per-hunt hunter highlights: every player's awards + damage share.

    Awards come from the REFramework mod (0..29); absent for fork-only hunts.
    """
    hunt = session.get(Hunt, hunt_id)
    if hunt is None:
        raise KeyError(hunt_id)
    monster = session.get(Monster, hunt.monster_id)
    hp_rows = session.execute(
        select(HuntPlayer, Player.display_name)
        .join(Player, Player.id == HuntPlayer.player_id)
        .where(HuntPlayer.hunt_id == hunt_id)
    ).all()
    award_rows = session.execute(
        select(HuntPlayerAward).where(HuntPlayerAward.hunt_id == hunt_id)
    ).scalars().all()
    meta = {a.id: a for a in session.execute(select(Award)).scalars()}
    by_player: dict[int, dict] = {}
    for hp, name in hp_rows:
        by_player[hp.player_id] = {
            "player_id": hp.player_id, "player": name,
            "is_supporter": bool(hp.is_supporter),
            "total_damage": hp.total_damage or 0.0, "awards": [],
        }
    present: set[int] = set()
    for a in award_rows:
        p = by_player.get(a.player_id)
        if p is None:
            continue
        entry: dict = {"id": a.award_id, "count": a.count}
        if a.channels:
            entry["channels"] = json.loads(a.channels)
        p["awards"].append(entry)
        present.add(a.award_id)
    party_total = sum(p["total_damage"] for p in by_player.values()
                      if not p["is_supporter"])
    for p in by_player.values():
        p["damage_share"] = (p["total_damage"] / party_total) if party_total else 0.0
        p["awards"].sort(key=lambda e: e["id"])
    awards_meta = []
    for aid in sorted(present, key=_award_sort_key):
        a = meta.get(aid)
        awards_meta.append({"id": aid,
                            "name": a.name if a else f"Award {aid}",
                            "explain": a.explain if a else None,
                            "unit": a.unit if a else 2})
    return {
        "hunt_id": hunt_id,
        "monster": monster.name if monster else None,
        "started_at": hunt.started_at.isoformat(),
        "cleared": bool(hunt.cleared),
        "awards": awards_meta,
        "players": sorted(by_player.values(),
                          key=lambda p: (-p["total_damage"], p["player"])),
    }


def highlights(session: Session, player_ids: list[int] | None = None,
               monster_id: int | None = None, stars: int | None = None,
               party: int | None = None,
               weapon_name: str | None = None,
               include_failed: bool = False) -> dict:
    """Aggregate hunter highlights across hunts: per-award player leaders
    (total / hunts-with / best) plus average damage share per player.

    Supporters are excluded. Filterable by monster / stars / weapon name /
    hunter scope / party size, matching every other view."""
    # Hunter scope and the weapon-name filter are HuntPlayer-level, so they
    # select *which hunts* are in play. The party used as the damage-share
    # denominator is always the full non-supporter party of each hunt (a
    # single-hunter scope would otherwise push every share to 100%).
    hunt_stmt = (select(HuntPlayer.hunt_id)
                 .join(Hunt, Hunt.id == HuntPlayer.hunt_id)
                 .where(filters.visible(), filters.cleared(include_failed)))
    if player_ids:
        hunt_stmt = hunt_stmt.where(HuntPlayer.player_id.in_(player_ids))
    if weapon_name is not None:
        hunt_stmt = hunt_stmt.where(HuntPlayer.weapon_name == weapon_name)
    if monster_id is not None:
        hunt_stmt = hunt_stmt.where(Hunt.monster_id == monster_id)
    if stars is not None:
        hunt_stmt = hunt_stmt.where(Hunt.quest_stars == stars)
    hunt_ids = [hid for (hid,) in
                session.execute(filters.party(hunt_stmt, party).distinct())]
    if not hunt_ids:
        return {"awards": [], "damage_share": []}

    meta = {a.id: a for a in session.execute(select(Award)).scalars()}
    award_stmt = (
        select(HuntPlayerAward.award_id, HuntPlayerAward.count,
               HuntPlayer.player_id, Player.display_name)
        .join(HuntPlayer, (HuntPlayerAward.hunt_id == HuntPlayer.hunt_id)
              & (HuntPlayerAward.player_id == HuntPlayer.player_id))
        .join(Player, Player.id == HuntPlayer.player_id)
        .where(HuntPlayerAward.hunt_id.in_(hunt_ids),
               HuntPlayer.is_supporter.is_(False)))
    if player_ids:
        award_stmt = award_stmt.where(HuntPlayer.player_id.in_(player_ids))
    agg: dict[tuple[int, int], dict] = {}
    for aid, count, pid, name in session.execute(award_stmt):
        d = agg.setdefault((aid, pid), {
            "player_id": pid, "player": name,
            "total": 0.0, "hunts": 0, "best": 0.0})
        c = count or 0
        d["total"] += c
        if c > 0:
            d["hunts"] += 1
        d["best"] = max(d["best"], c)
    by_award: dict[int, list] = {}
    for (aid, _pid), d in agg.items():
        if d["total"] > 0:  # hide players who scored nothing on an award
            by_award.setdefault(aid, []).append(d)
    awards_out = []
    for aid in sorted(by_award, key=_award_sort_key):
        a = meta.get(aid)
        leaders = sorted(by_award[aid], key=lambda x: (-x["total"], x["player"]))
        awards_out.append({
            "id": aid, "name": a.name if a else f"Award {aid}",
            "explain": a.explain if a else None,
            "unit": a.unit if a else 2,
            "leaders": leaders[:25],
        })

    # Average damage share: one query, then each hunt's denominator is the
    # full non-supporter party; only the emitted rows follow the hunter scope.
    ds_stmt = (
        select(HuntPlayer.hunt_id, HuntPlayer.player_id,
               Player.display_name, HuntPlayer.total_damage)
        .join(Player, Player.id == HuntPlayer.player_id)
        .where(HuntPlayer.hunt_id.in_(hunt_ids),
               HuntPlayer.is_supporter.is_(False)))
    rows = session.execute(ds_stmt).all()
    party_totals: dict[int, float] = {}
    for hid, _pid, _name, dmg in rows:
        party_totals[hid] = party_totals.get(hid, 0.0) + (dmg or 0.0)
    scope = set(player_ids) if player_ids else None
    per_player: dict[int, dict] = {}
    for hid, pid, name, dmg in rows:
        if scope is not None and pid not in scope:
            continue
        total = party_totals.get(hid, 0.0)
        d = per_player.setdefault(pid, {"player_id": pid, "player": name,
                                        "shares": [], "hunts": set()})
        d["hunts"].add(hid)
        if total > 0:
            d["shares"].append((dmg or 0.0) / total)
    damage_share = [{
        "player_id": d["player_id"], "player": d["player"],
        "avg_share": sum(d["shares"]) / len(d["shares"]) if d["shares"] else 0.0,
        "hunts": len(d["hunts"]),
    } for d in per_player.values()]
    damage_share.sort(key=lambda x: (-x["avg_share"], x["player"]))
    return {"awards": awards_out, "damage_share": damage_share}


def _median(vals: list[float]) -> float:
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def _slope_per_hunt(vals: list[float]) -> float:
    """Least-squares slope of DPS over hunt index (DPS gained per hunt)."""
    n = len(vals)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2.0
    mean_y = sum(vals) / n
    denom = sum((i - mean_x) ** 2 for i in range(n))
    if not denom:
        return 0.0
    return sum((i - mean_x) * (y - mean_y) for i, y in enumerate(vals)) / denom


def progress_improvement(session: Session, player_id: int | None = None, top_n: int = 5,
                         weapon_id: int | None = None,
                         player_ids: list[int] | None = None,
                         monster_id: int | None = None,
                         stars: int | None = None,
                         variant_id: int | str | None = None,
                         party: int | None = None,
                         weapon_name: str | None = None,
                         include_failed: bool = False) -> dict:
    """Analyze player DPS improvement over time, grouped by monster and quest stars (only groups with >1 instance).

    Single-hunter mode (``player_id`` set, no ``player_ids``) returns one
    player dict with ``groups``. Otherwise returns ``{"top_hunters": [...]}``
    ranked by instance-weighted overall improvement. ``player_ids`` narrows
    the ranking (multi-hunter scope); ``monster_id``/``stars``/``weapon_id``/
    ``variant_id`` narrow the hunts considered.
    """
    top_n = max(1, min(int(top_n or 5), 25))
    players = session.execute(select(Player)).scalars().all()
    player_map = {p.id: p.display_name for p in players}

    # Single-hunter detail vs ranked list.
    single_id = player_id if not player_ids else None

    stmt = (
        select(Hunt, HuntPlayer, Player, Monster)
        .join(HuntPlayer, HuntPlayer.hunt_id == Hunt.id)
        .join(Player, Player.id == HuntPlayer.player_id)
        .join(Monster, Monster.id == Hunt.monster_id)
        .where(filters.cleared(include_failed), HuntPlayer.is_supporter.is_(False),
               filters.visible())
        .order_by(Hunt.started_at)
    )
    if single_id is not None:
        stmt = stmt.where(HuntPlayer.player_id == single_id)
    elif player_ids:
        stmt = stmt.where(HuntPlayer.player_id.in_(player_ids))
    if weapon_id is not None:
        stmt = stmt.where(HuntPlayer.weapon_id == weapon_id)
    if weapon_name is not None:
        stmt = stmt.where(HuntPlayer.weapon_name == weapon_name)
    if monster_id is not None:
        stmt = stmt.where(Hunt.monster_id == monster_id)
    if stars is not None:
        stmt = stmt.where(Hunt.quest_stars == stars)
    stmt = filters.party(stmt, party)

    # Variant narrowing only applies with an explicit hunter scope
    # (mirrors resolve_variant_filter semantics).
    scope_for_variant = ([single_id] if single_id is not None
                         else list(player_ids or []))
    variant_hunts = resolve_variant_filter(session, scope_for_variant or None,
                                            variant_id)
    if variant_hunts is not None:
        if not variant_hunts:
            if single_id is not None:
                name = player_map.get(single_id, f"Player {single_id}")
                return {"player_id": single_id, "player_name": name,
                        "overall_pct_improvement": 0.0,
                        "qualifying_groups_count": 0, "groups": []}
            return {"top_hunters": []}
        stmt = stmt.where(Hunt.id.in_(variant_hunts))

    player_data: dict[int, dict[tuple[int, str, int | None], list[dict]]] = {}

    imp_rows = list(session.execute(stmt))
    imp_hunts = {h.id: h for h, _hp, _p, _m in imp_rows}
    imp_eng, imp_cap = _dps_windows(
        session, imp_hunts, [(h.id, hp.player_id) for h, hp, _p, _m in imp_rows])
    for hunt, hp, player, monster in imp_rows:
        dur = imp_eng.get((hunt.id, hp.player_id))
        dps = (imp_cap.get((hunt.id, hp.player_id), hp.total_damage) / dur) if dur else 0.0
        stars_val = hunt.quest_stars
        key = (monster.id, monster.name, stars_val)

        p_groups = player_data.setdefault(player.id, {})
        group_hunts = p_groups.setdefault(key, [])
        group_hunts.append({
            "hunt_id": hunt.id,
            "started_at": hunt.started_at.isoformat(),
            "dps": dps,
            "clear_s": hunt_duration_s(hunt),
        })

    def analyze_player(pid: int, groups_dict: dict) -> dict:
        p_name = player_map.get(pid, f"Player {pid}")
        qualifying_groups = []
        weighted_sum = 0.0
        weighted_n = 0

        for (mid, mname, st), hunts in groups_dict.items():
            if len(hunts) > 1:
                dps_vals = [h["dps"] for h in hunts]
                first_dps = dps_vals[0]
                latest_dps = dps_vals[-1]
                pct = ((latest_dps - first_dps) / first_dps * 100.0) if first_dps > 0 else 0.0
                first_clear = hunts[0]["clear_s"]
                latest_clear = hunts[-1]["clear_s"]
                clear_pct = (((first_clear - latest_clear) / first_clear * 100.0)
                             if first_clear and latest_clear and first_clear > 0 else 0.0)
                qualifying_groups.append({
                    "monster_id": mid,
                    "monster_name": mname,
                    "stars": st,
                    "instances": len(hunts),
                    "first_dps": round(first_dps, 1),
                    "latest_dps": round(latest_dps, 1),
                    "median_dps": round(_median(dps_vals), 1),
                    "best_dps": round(max(dps_vals), 1),
                    "slope_per_hunt": round(_slope_per_hunt(dps_vals), 2),
                    "pct_improvement": round(pct, 1),
                    "first_clear_s": round(first_clear) if first_clear else None,
                    "latest_clear_s": round(latest_clear) if latest_clear else None,
                    "clear_pct_improvement": round(clear_pct, 1),
                    "hunts": hunts,
                })
                weighted_sum += pct * len(hunts)
                weighted_n += len(hunts)

        overall = (weighted_sum / weighted_n) if weighted_n else 0.0
        qualifying_groups.sort(key=lambda g: g["pct_improvement"], reverse=True)
        return {
            "player_id": pid,
            "player_name": p_name,
            "overall_pct_improvement": round(overall, 1),
            "qualifying_groups_count": len(qualifying_groups),
            "groups": qualifying_groups,
        }

    if single_id is not None:
        if single_id not in player_data:
            return {"player_id": single_id,
                    "player_name": player_map.get(single_id, f"Player {single_id}"),
                    "overall_pct_improvement": 0.0,
                    "qualifying_groups_count": 0, "groups": []}
        return analyze_player(single_id, player_data[single_id])
    else:
        results = []
        for pid, groups_dict in player_data.items():
            res = analyze_player(pid, groups_dict)
            if res["qualifying_groups_count"] > 0:
                results.append(res)
        results.sort(key=lambda r: r["overall_pct_improvement"], reverse=True)
        return {"top_hunters": results[:top_n]}



def list_aliases(session: Session) -> dict:
    """Rename-variant sightings awaiting review (oldest first)."""
    rows = session.execute(
        select(PlayerAlias, Player.display_name)
        .join(Player, Player.id == PlayerAlias.player_id)
        .order_by(PlayerAlias.created_at)
    ).all()
    return {"aliases": [{
        "id": a.id, "alias": a.alias, "player_id": pid,
        "player": pname, "created_at": a.created_at.isoformat(),
    } for a, pname in rows for pid in (a.player_id,)]}


def dismiss_alias(session: Session, alias_id: int) -> dict:
    """Drop a review item, keeping the players separate (explicit keep)."""
    row = session.get(PlayerAlias, alias_id)
    if row is None:
        raise KeyError(alias_id)
    session.delete(row)
    session.commit()
    return {"id": alias_id, "dismissed": True}


def merge_alias(session: Session, alias_id: int) -> dict:
    """Merge the alias-named player into the alias target (explicit merge).

    Every FK row of the source player (hunt memberships, snapshots,
    abnormalities, pins) is reassigned to the target; same-hunt
    memberships combine damage; then the source row and alias die.
    """
    alias = session.get(PlayerAlias, alias_id)
    if alias is None:
        raise KeyError(alias_id)
    source = session.execute(
        select(Player).where(Player.display_name == alias.alias)
    ).scalar_one_or_none()
    target = session.get(Player, alias.player_id)
    if source is None or target is None or source.id == target.id:
        raise KeyError(alias_id)
    moved = {"hunts": 0, "snapshots": 0, "abnormalities": 0}
    for hp in session.execute(
            select(HuntPlayer).where(HuntPlayer.player_id == source.id)
    ).scalars().all():
        clash = session.get(HuntPlayer, (hp.hunt_id, target.id))
        if clash is None:
            hp.player_id = target.id
        else:
            clash.total_damage = (clash.total_damage or 0.0) + (hp.total_damage or 0.0)
            clash.peak_dps = max(clash.peak_dps or 0.0, hp.peak_dps or 0.0)
            session.delete(hp)
        moved["hunts"] += 1
    for snap in session.execute(
            select(DpsSnapshot).where(DpsSnapshot.player_id == source.id)
    ).scalars().all():
        snap.player_id = target.id
        moved["snapshots"] += 1
    for ab in session.execute(
            select(PlayerAbnormality).where(PlayerAbnormality.player_id == source.id)
    ).scalars().all():
        ab.player_id = target.id
        moved["abnormalities"] += 1
    if session.get(PlayerPin, target.id) is None and \
            session.get(PlayerPin, source.id) is not None:
        session.add(PlayerPin(player_id=target.id))
    old_pin = session.get(PlayerPin, source.id)
    if old_pin is not None:
        session.delete(old_pin)
    session.delete(source)
    session.delete(alias)
    session.commit()
    return {"id": alias_id, "merged": alias.alias, "into": target.display_name,
            **moved}
