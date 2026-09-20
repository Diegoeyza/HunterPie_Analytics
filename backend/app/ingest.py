"""Phase 1 data-layer logic: identity resolution + idempotent hunt upsert.

Rules (from PLAN + review):
- Exact display_name match wins. Case-insensitive-only matches are FLAGGED
  for manual review, never silently merged (FR-2.2).
- Dedup: HunterPie quest/session ID when present, else composite
  dedup_hash(monster_id, sorted player ids-or-names, start_ts rounded to 1s).
- One DB transaction per hunt: crash mid-hunt must not leave orphans.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import (
    DpsSnapshot,
    Hunt,
    HuntPlayer,
    MonsterEvent,
    MonsterHealthStep,
    Player,
    PlayerAbnormality,
    PlayerAlias,
    Weapon,
    WeaponIdentity,
)

log = logging.getLogger(__name__)

REQUIRED_HUNT_FIELDS = (
    "monster_id",
    "started_at",
    "hunterpie_version",
    "game_version",
)


def _coerce_ts(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is None else value.astimezone(UTC).replace(tzinfo=None)
    return datetime.fromisoformat(value)


def _canonical(display_name: str) -> str:
    return display_name.casefold()


def compute_dedup_hash(monster_id: int, player_keys: list[str], started_at: datetime | str) -> str:
    ts = _coerce_ts(started_at).replace(microsecond=0).isoformat()
    core = "|".join([str(monster_id), ",".join(sorted(player_keys)), ts])
    return hashlib.sha256(core.encode()).hexdigest()[:32]


def find_hunt_by_payload(session: Session, payload: dict) -> Hunt | None:
    """Cheap pre-check: content dedup hit without touching reference rows.

    Lets callers skip ensure_monster/ensure_weapon (and their commit) for
    files that are already imported.

    Match order: (quest_id_external, monster_id) first — stable across
    renames/reorders — then the composite dedup_hash fallback.
    """
    quest_id = payload.get("quest_id_external")
    if quest_id:
        hit = session.execute(
            select(Hunt).where(Hunt.quest_id_external == quest_id,
                               Hunt.monster_id == payload["monster_id"])
        ).scalar_one_or_none()
        if hit is not None:
            return hit
    dh = payload.get("dedup_hash")
    if not dh:
        names = sorted(p["display_name"] for p in payload.get("players", []))
        dh = compute_dedup_hash(
            payload["monster_id"], names, _coerce_ts(payload["started_at"]))
    return session.execute(
        select(Hunt).where(Hunt.dedup_hash == dh)
    ).scalar_one_or_none()


def find_rename_candidates(session: Session, display_name: str) -> list[Player]:
    """Existing players matching case-insensitively but not exactly.

    Compares on lower(display_name) directly (not the canonical column)
    so legacy rows without a backfilled canonical still match.
    """
    return list(
        session.execute(
            select(Player).where(func.lower(Player.display_name)
                                 == display_name.lower(),
                                 Player.display_name != display_name)
        ).scalars()
    )


def get_or_create_player(
    session: Session, display_name: str, now: datetime, warnings: list[str]
) -> Player:
    exact = session.execute(
        select(Player).where(Player.display_name == display_name)
    ).scalar_one_or_none()
    if exact is not None:
        if exact.canonical is None:
            exact.canonical = _canonical(display_name)
        return exact
    candidates = find_rename_candidates(session, display_name)
    if candidates:
        warnings.append(
            f"rename-review: '{display_name}' resembles "
            + ", ".join(f"'{c.display_name}' (id={c.id})" for c in candidates)
        )
    player = Player(display_name=display_name,
                    canonical=_canonical(display_name), first_seen_at=now)
    session.add(player)
    session.flush()
    # Persist the sighting for the review queue (Phase 4 UI); never merge.
    # Each insert runs in a savepoint so a duplicate alias can't poison
    # the surrounding hunt transaction.
    for c in candidates:
        try:
            with session.begin_nested():
                session.add(PlayerAlias(alias=display_name, player_id=c.id))
        except IntegrityError:
            pass  # already recorded; keep going
    return player


def get_or_create_identity(session: Session, weapon_type: str,
                             gear: dict) -> WeaponIdentity:
    """First sighting of a gear fingerprint auto-creates an unlabeled
    identity row; the user names it once in the dashboard."""
    identity = session.execute(
        select(WeaponIdentity).where(
            WeaponIdentity.weapon_type == weapon_type,
            WeaponIdentity.gear_raw == gear["raw"],
            WeaponIdentity.gear_element == gear["element"],
            WeaponIdentity.gear_affinity == gear["affinity"],
        )
    ).scalar_one_or_none()
    if identity is None:
        identity = WeaponIdentity(
            weapon_type=weapon_type,
            gear_raw=gear["raw"],
            gear_element=gear["element"],
            gear_affinity=gear["affinity"],
        )
        session.add(identity)
        session.flush()
    return identity


def _nonneg(value, field: str) -> None:
    if value is not None and value < 0:
        raise ValueError(f"{field} must be >= 0, got {value!r}")


def _validate_payload_numbers(payload: dict) -> None:
    """Reject corrupt frames loudly (never silently ingest garbage)."""
    for p in payload.get("players", []):
        _nonneg(p.get("total_damage", 0),
                f"total_damage for {p.get('display_name')!r}")
        _nonneg(p.get("peak_dps", 0),
                f"peak_dps for {p.get('display_name')!r}")
        gear = p.get("gear") or {}
        _nonneg(gear.get("raw"), f"gear.raw for {p.get('display_name')!r}")
        _nonneg(gear.get("element"),
                f"gear.element for {p.get('display_name')!r}")
        aff = gear.get("affinity")
        if aff is not None and not -100 <= aff <= 100:
            raise ValueError(
                f"gear.affinity for {p.get('display_name')!r} must be "
                f"-100..100, got {aff!r}")
    for s in payload.get("snapshots", []):
        _nonneg(s.get("ts_offset_seconds"), "snapshot ts_offset_seconds")
        _nonneg(s.get("cumulative_damage", 0), "snapshot cumulative_damage")
    for e in payload.get("events", []):
        _nonneg(e.get("start_offset_seconds"), "event start_offset_seconds")
        end = e.get("end_offset_seconds")
        if end is not None and end < (e.get("start_offset_seconds") or 0):
            raise ValueError("event end precedes start")
    for h in payload.get("hp_steps", []):
        frac = h.get("hp_fraction")
        if frac is not None and not 0 <= frac <= 1:
            raise ValueError(f"hp_fraction must be 0..1, got {frac!r}")


def upsert_hunt(session: Session, payload: dict,
                cache: dict | None = None) -> tuple[Hunt, bool, list[str]]:
    """Insert one hunt atomically. Returns (hunt, created, warnings). Idempotent.

    cache: optional per-import-job dict memoizing ("player", name) -> id and
    ("identity", weapon_type, raw, element, affinity) -> id, so bulk imports
    don't re-SELECT the same reference rows for every hunt.
    """
    missing = [f for f in REQUIRED_HUNT_FIELDS if payload.get(f) is None]
    if missing:
        raise ValueError(f"missing required hunt fields: {missing}")
    if not payload.get("players"):
        raise ValueError("hunt must include at least one player")

    warnings: list[str] = []
    now = datetime.now(UTC).replace(tzinfo=None)
    started_at = _coerce_ts(payload["started_at"])
    ended_at = _coerce_ts(payload["ended_at"]) if payload.get("ended_at") else None
    if ended_at is not None and ended_at < started_at:
        raise ValueError("ended_at precedes started_at")
    _validate_payload_numbers(payload)
    player_names = sorted(p["display_name"] for p in payload["players"])
    quest_id = payload.get("quest_id_external")
    cache = cache if cache is not None else {}

    existing = find_hunt_by_payload(session, payload)
    if existing is not None:
        return existing, False, warnings

    try:
        quest_damage = sum(float(p.get("total_damage", 0))
                           for p in payload["players"])
        hunt = Hunt(
            quest_id_external=quest_id,
            dedup_hash=payload.get("dedup_hash")
            or compute_dedup_hash(payload["monster_id"], player_names, started_at),
            monster_id=payload["monster_id"],
            quest_id=payload.get("quest_id"),
            quest_type=payload.get("quest_type"),
            quest_level=payload.get("quest_level"),
            quest_stars=payload.get("quest_stars"),
            monster_max_hp=payload.get("monster_max_hp"),
            monster_variant=payload.get("monster_variant"),
            monster_crown=payload.get("monster_crown"),
            started_at=started_at,
            ended_at=ended_at,
            quest_time_seconds=payload.get("quest_time_seconds"),
            real_hunt_time_seconds=payload.get("real_hunt_time_seconds"),
            cart_count=payload.get("cart_count", 0),
            cleared=bool(payload.get("cleared", False)),
            player_count=payload.get("player_count", len(payload["players"])),
            is_sos=bool(payload.get("is_sos", False)),
            joined_mid_hunt=bool(payload.get("joined_mid_hunt", False)),
            quest_damage=quest_damage,
            is_split_quest=bool(payload.get("is_split_quest", False)),
            hunterpie_version=payload["hunterpie_version"],
            game_version=payload["game_version"],
        )
        if hunt.is_sos or hunt.joined_mid_hunt:
            warnings.append("untrusted-flags: is_sos/joined_mid_hunt set — verify before trusting stats")
            log.debug("hunt %s has untrusted SOS/mid-join flags", quest_id)
        session.add(hunt)
        session.flush()

        player_ids: dict[str, int] = {}
        for p in payload["players"]:
            pkey = ("player", p["display_name"])
            pid = cache.get(pkey)
            if pid is None:
                player = get_or_create_player(session, p["display_name"], now, warnings)
                pid = player.id
                cache[pkey] = pid
            player_ids[p["display_name"]] = pid
            gear = p.get("gear") or {}
            if gear and {"raw", "element", "affinity"} <= set(gear):
                weapon = session.get(Weapon, p.get("weapon_id"))
                wtype = weapon.name if weapon else "Unknown"
                ikey = ("identity", wtype, gear["raw"], gear["element"],
                        gear["affinity"])
                if ikey not in cache:
                    cache[ikey] = get_or_create_identity(session, wtype, gear).id
            else:
                gear = {}
            session.add(
                HuntPlayer(
                    hunt_id=hunt.id,
                    player_id=pid,
                    weapon_id=p.get("weapon_id"),
                    total_damage=p.get("total_damage", 0),
                    peak_dps=p.get("peak_dps", 0),
                    is_supporter=bool(p.get("is_supporter", False)),
                    gear_raw=gear.get("raw"),
                    gear_element=gear.get("element"),
                    gear_affinity=gear.get("affinity"),
                )
            )
        for s in payload.get("snapshots", []):
            if s["display_name"] not in player_ids:
                raise ValueError(
                    f"snapshot references unknown player '{s['display_name']}'"
                )
            session.add(
                DpsSnapshot(
                    hunt_id=hunt.id,
                    player_id=player_ids[s["display_name"]],
                    ts_offset_seconds=s["ts_offset_seconds"],
                    cumulative_damage=s.get("cumulative_damage", 0),
                    instant_dps=s.get("instant_dps", 0),
                )
            )
        for e in payload.get("events", []):
            session.add(
                MonsterEvent(
                    hunt_id=hunt.id,
                    monster_id=hunt.monster_id,
                    event_type=e["event_type"],
                    start_offset_seconds=e["start_offset_seconds"],
                    end_offset_seconds=e.get("end_offset_seconds"),
                )
            )
        for h in payload.get("hp_steps", []):
            session.add(
                MonsterHealthStep(
                    hunt_id=hunt.id,
                    monster_id=hunt.monster_id,
                    ts_offset_seconds=h["ts_offset_seconds"],
                    hp_fraction=h["hp_fraction"],
                )
            )
        for a in payload.get("abnormalities", []):
            if a["display_name"] not in player_ids:
                continue
            session.add(
                PlayerAbnormality(
                    hunt_id=hunt.id,
                    player_id=player_ids[a["display_name"]],
                    abnormality_id=a["abnormality_id"],
                    category=a["category"],
                    started_at_offset=a["started_at_offset"],
                    finished_at_offset=a.get("finished_at_offset"),
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return hunt, True, warnings
