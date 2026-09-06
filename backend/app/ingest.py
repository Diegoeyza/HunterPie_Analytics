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
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import DpsSnapshot, Hunt, HuntPlayer, MonsterEvent, MonsterHealthStep, Player

REQUIRED_HUNT_FIELDS = (
    "monster_id",
    "started_at",
    "hunterpie_version",
    "game_version",
)


def _coerce_ts(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is None else value.astimezone(timezone.utc).replace(tzinfo=None)
    return datetime.fromisoformat(value)


def compute_dedup_hash(monster_id: int, player_keys: list[str], started_at: datetime | str) -> str:
    ts = _coerce_ts(started_at).replace(microsecond=0).isoformat()
    core = "|".join([str(monster_id), ",".join(sorted(player_keys)), ts])
    return hashlib.sha256(core.encode()).hexdigest()[:32]


def find_rename_candidates(session: Session, display_name: str) -> list[Player]:
    """Return existing players matching case-insensitively but not exactly."""
    exact = session.execute(
        select(Player).where(Player.display_name == display_name)
    ).scalar_one_or_none()
    if exact is not None:
        return []
    return list(
        session.execute(
            select(Player).where(func.lower(Player.display_name) == display_name.lower())
        ).scalars()
    )


def get_or_create_player(
    session: Session, display_name: str, now: datetime, warnings: list[str]
) -> Player:
    exact = session.execute(
        select(Player).where(Player.display_name == display_name)
    ).scalar_one_or_none()
    if exact is not None:
        return exact
    candidates = find_rename_candidates(session, display_name)
    if candidates:
        warnings.append(
            f"rename-review: '{display_name}' resembles "
            + ", ".join(f"'{c.display_name}' (id={c.id})" for c in candidates)
        )
    player = Player(display_name=display_name, first_seen_at=now)
    session.add(player)
    session.flush()
    return player


def upsert_hunt(session: Session, payload: dict) -> tuple[Hunt, bool, list[str]]:
    """Insert one hunt atomically. Returns (hunt, created, warnings). Idempotent."""
    missing = [f for f in REQUIRED_HUNT_FIELDS if payload.get(f) is None]
    if missing:
        raise ValueError(f"missing required hunt fields: {missing}")
    if not payload.get("players"):
        raise ValueError("hunt must include at least one player")

    warnings: list[str] = []
    now = datetime.utcnow()
    started_at = _coerce_ts(payload["started_at"])
    player_names = sorted(p["display_name"] for p in payload["players"])
    quest_id = payload.get("quest_id_external")

    existing: Hunt | None = None
    if quest_id:
        existing = session.execute(
            select(Hunt).where(Hunt.quest_id_external == quest_id)
        ).scalar_one_or_none()
    if existing is None:
        dedup_hash = payload.get("dedup_hash") or compute_dedup_hash(
            payload["monster_id"], player_names, started_at
        )
        existing = session.execute(
            select(Hunt).where(Hunt.dedup_hash == dedup_hash)
        ).scalar_one_or_none()
    else:
        dedup_hash = existing.dedup_hash
    if existing is not None:
        return existing, False, warnings

    try:
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
            ended_at=_coerce_ts(payload["ended_at"]) if payload.get("ended_at") else None,
            quest_time_seconds=payload.get("quest_time_seconds"),
            real_hunt_time_seconds=payload.get("real_hunt_time_seconds"),
            cart_count=payload.get("cart_count", 0),
            cleared=bool(payload.get("cleared", False)),
            player_count=payload.get("player_count", len(payload["players"])),
            is_sos=bool(payload.get("is_sos", False)),
            joined_mid_hunt=bool(payload.get("joined_mid_hunt", False)),
            hunterpie_version=payload["hunterpie_version"],
            game_version=payload["game_version"],
        )
        if hunt.is_sos or hunt.joined_mid_hunt:
            warnings.append("untrusted-flags: is_sos/joined_mid_hunt set — verify before trusting stats")
        session.add(hunt)
        session.flush()

        player_ids: dict[str, int] = {}
        for p in payload["players"]:
            player = get_or_create_player(session, p["display_name"], now, warnings)
            player_ids[p["display_name"]] = player.id
            session.add(
                HuntPlayer(
                    hunt_id=hunt.id,
                    player_id=player.id,
                    weapon_id=p.get("weapon_id"),
                    total_damage=p.get("total_damage", 0),
                    peak_dps=p.get("peak_dps", 0),
                    is_supporter=bool(p.get("is_supporter", False)),
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
        session.commit()
    except Exception:
        session.rollback()
        raise
    return hunt, True, warnings
