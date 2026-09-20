"""Weapon-variant (gear fingerprint) clustering + filter resolution.

The fork exports no weapon names, only (type, raw, element, affinity).
Fingerprints with near-identical stats are grouped so the dashboard can
offer each build as one selectable variant; the user names builds once
(WeaponIdentity.label) and every matching hunt resolves.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .filters import visible
from .models import Hunt, HuntPlayer, Weapon, WeaponIdentity

UNKNOWN_VARIANT_ID = 0
"""Pseudo variant id for hunts with no gear data (pre-gear fork exports)."""

VARIANT_GROUP_RAW_TOL = 0.10
"""Max relative raw gap inside one weapon group (Balanced)."""
VARIANT_GROUP_ELE_TOL = 0.15
"""Max relative element gap inside one weapon group (element swings more)."""
VARIANT_GROUP_ELE_FLOOR = 50.0
"""Absolute element gap always tolerated below this (negligible element)."""
VARIANT_GROUP_AFF_TOL = 10.0
"""Max affinity-points gap inside one weapon group."""


def variant_stats_similar(a: dict, b: dict) -> bool:
    """True when two fingerprints of the same weapon type fight alike.

    Raw within 10% relative; element within 15% relative (or a negligible
    absolute gap), with raw-vs-elemental (one side zero) never similar;
    affinity within 10 points.
    """
    raw_lo, raw_hi = sorted((a["raw"], b["raw"]))
    if raw_hi <= 0 or (raw_hi - raw_lo) / raw_hi > VARIANT_GROUP_RAW_TOL:
        return False
    ea, eb = a["element"], b["element"]
    if (ea == 0) != (eb == 0):
        return False
    if ea or eb:
        elo, ehi = sorted((ea, eb))
        if (ehi - elo) > VARIANT_GROUP_ELE_FLOOR and \
                (ehi - elo) / ehi > VARIANT_GROUP_ELE_TOL:
            return False
    if abs(a["affinity"] - b["affinity"]) > VARIANT_GROUP_AFF_TOL:
        return False
    return True


def cluster_weapon_variants(fps: list[dict]) -> list[list[dict]]:
    """Group fingerprints into similar-stat builds (complete linkage).

    Clustering runs per weapon type over (raw, element, affinity); each
    fingerprint joins the first group whose every member is similar, else
    it starts a new one. Input order is normalized first, so group
    assignment is deterministic for the same rows. Returns non-empty
    groups, each with 1+ members.
    """
    by_type: dict[str, list[dict]] = {}
    for fp in sorted(fps, key=lambda f: (f["weapon_type"], f["raw"],
                                         f["element"], f["affinity"])):
        by_type.setdefault(fp["weapon_type"], []).append(fp)
    out = []
    for wtype in sorted(by_type):
        groups: list[list[dict]] = []
        for fp in by_type[wtype]:
            for g in groups:
                if all(variant_stats_similar(fp, m) for m in g):
                    g.append(fp)
                    break
            else:
                groups.append([fp])
        out.extend(sorted(groups, key=lambda g: (g[0]["raw"], g[0]["element"],
                                                 g[0]["affinity"])))
    return out


def variant_group_key(weapon_type: str, index: int) -> str:
    """Stable selector key for the ``index``-th group of a weapon type."""
    return f"g:{weapon_type}:{index}"


def group_player_variants(fps: list[dict]) -> dict[int, str]:
    """Map each fingerprint's position to its group key.

    ``fps`` carries an ``_pos`` field; split of cluster_weapon_variants
    output back onto the caller's rows.
    """
    key_by_pos: dict[int, str] = {}
    counters: dict[str, int] = {}
    for group in cluster_weapon_variants(fps):
        wtype = group[0]["weapon_type"]
        key = variant_group_key(wtype, counters.get(wtype, 0))
        counters[wtype] = counters.get(wtype, 0) + 1
        for fp in group:
            key_by_pos[fp["_pos"]] = key
    return key_by_pos


def player_variant_rows(session: Session, player_id: int) -> list[dict]:
    """Player's distinct gear fingerprints as plain dicts (positioned)."""
    rows = session.execute(
        select(Weapon.name, HuntPlayer.gear_raw, HuntPlayer.gear_element,
               HuntPlayer.gear_affinity,
               func.count(func.distinct(HuntPlayer.hunt_id)))
        .outerjoin(Weapon, Weapon.id == HuntPlayer.weapon_id)
        .join(Hunt, Hunt.id == HuntPlayer.hunt_id)
        .where(HuntPlayer.player_id == player_id,
               HuntPlayer.gear_raw.is_not(None), visible())
        .group_by(Weapon.name, HuntPlayer.gear_raw, HuntPlayer.gear_element,
                  HuntPlayer.gear_affinity)
    ).all()
    fps = []
    for pos, (wname, raw, element, affinity, hunts) in enumerate(rows):
        fps.append({"_pos": pos, "weapon_type": wname or "Unknown",
                    "raw": raw, "element": element, "affinity": affinity,
                    "hunts": hunts})
    groups = group_player_variants(fps)
    for fp in fps:
        fp["group"] = groups[fp["_pos"]]
    return fps


def variant_hunt_ids(session: Session, player_id: int,
                     variant_id: int | str) -> set[int]:
    """Hunt ids where ``player_id`` fought with the given weapon variant.

    ``variant_id`` is a WeaponIdentity id, a ``g:<type>:<n>`` group key
    (union over the group's fingerprints), or UNKNOWN_VARIANT_ID for hunts
    with NULL gear columns. Unknown ids/keys yield the empty set.
    """
    if isinstance(variant_id, str) and variant_id.startswith("g:"):
        fps = [fp for fp in player_variant_rows(session, player_id)
               if fp["group"] == variant_id]
        if not fps:
            return set()
        from sqlalchemy import and_ as _and
        from sqlalchemy import or_ as _or
        stmt = (select(HuntPlayer.hunt_id)
                .where(HuntPlayer.player_id == player_id)
                .where(_or(*[_and(HuntPlayer.gear_raw == fp["raw"],
                                  HuntPlayer.gear_element == fp["element"],
                                  HuntPlayer.gear_affinity == fp["affinity"])
                             for fp in fps])))
    else:
        try:
            variant_id = int(variant_id)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return set()
        stmt = select(HuntPlayer.hunt_id).where(HuntPlayer.player_id == player_id)
        if variant_id == UNKNOWN_VARIANT_ID:
            stmt = stmt.where(HuntPlayer.gear_raw.is_(None))
            stmt = stmt.join(Hunt, Hunt.id == HuntPlayer.hunt_id).where(visible())
            return set(session.execute(stmt).scalars())
        identity = session.get(WeaponIdentity, variant_id)
        if identity is None:
            return set()
        stmt = stmt.where(
            HuntPlayer.gear_raw == identity.gear_raw,
            HuntPlayer.gear_element == identity.gear_element,
            HuntPlayer.gear_affinity == identity.gear_affinity,
        )
    stmt = stmt.join(Hunt, Hunt.id == HuntPlayer.hunt_id).where(visible())
    return set(session.execute(stmt).scalars())


def resolve_variant_filter(session: Session,
                           player_ids: list[int] | None,
                           variant_id: int | str | None) -> set[int] | None:
    """Shared variant narrowing for scoped queries.

    Only applies with exactly one scoped hunter (the dashboard only offers
    the filter then); otherwise returns None = no narrowing.
    """
    if variant_id is None or not player_ids or len(player_ids) != 1:
        return None
    return variant_hunt_ids(session, player_ids[0], variant_id)


def identity_label_map(session: Session) -> dict[tuple, str | None]:
    """(weapon_type, raw, element, affinity) -> user label (or None)."""
    return {(i.weapon_type, i.gear_raw, i.gear_element, i.gear_affinity): i.label
            for i in session.execute(select(WeaponIdentity)).scalars()}


def gear_variant_label(label_map: dict[tuple, str | None], weapon_name: str | None,
                       raw: float | None, element: float | None,
                       affinity: float | None) -> str | None:
    if raw is None:
        return None
    return label_map.get((weapon_name or "Unknown", raw, element, affinity))


def player_variants(session: Session, player_id: int) -> dict:
    """Distinct gear fingerprints used by one hunter, with hunt counts.

    Each variant carries its similarity ``group`` key (``g:<type>:<n>``);
    fingerprints with near-identical stats share a group so the dashboard
    can offer them as one selectable build.
    """
    fps = player_variant_rows(session, player_id)
    identities = {(i.weapon_type, i.gear_raw, i.gear_element, i.gear_affinity): i
                  for i in session.execute(select(WeaponIdentity)).scalars()}
    variants = []
    for fp in fps:
        identity = identities.get((fp["weapon_type"], fp["raw"],
                                   fp["element"], fp["affinity"]))
        variants.append({
            "id": identity.id if identity else None,
            "weapon_type": fp["weapon_type"],
            "raw": fp["raw"], "element": fp["element"],
            "affinity": fp["affinity"],
            "label": identity.label if identity else None,
            "hunts": fp["hunts"],
            "group": fp["group"],
        })
    unknown = session.execute(
        select(func.count(func.distinct(HuntPlayer.hunt_id)))
        .join(Hunt, Hunt.id == HuntPlayer.hunt_id)
        .where(HuntPlayer.player_id == player_id,
               HuntPlayer.gear_raw.is_(None), visible())
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
