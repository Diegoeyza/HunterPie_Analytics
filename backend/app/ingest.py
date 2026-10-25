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
import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .abnormalities import AbnormalityId
from .models import (
    Award,
    DpsSnapshot,
    Hunt,
    HuntPlayer,
    HuntPlayerAward,
    MonsterEvent,
    MonsterHealthStep,
    Player,
    PlayerAbnormality,
    PlayerAlias,
    PlayerHealthStep,
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


def _shift_payload_offsets(payload: dict, delta: float) -> None:
    """Move every offset in a payload by `delta` seconds.

    Used when the incoming dump's clock starts later than the hunt's (the
    companion attached mid-hunt): its offsets are attach-relative, so the
    true quest timeline needs them pushed later."""
    for x in payload.get("snapshots", []):
        x["ts_offset_seconds"] += delta
    for x in payload.get("events", []):
        x["start_offset_seconds"] += delta
        if x.get("end_offset_seconds") is not None:
            x["end_offset_seconds"] += delta
    for x in payload.get("hp_steps", []):
        x["ts_offset_seconds"] += delta
    for x in payload.get("player_health", []):
        x["ts_offset_seconds"] += delta
    for x in payload.get("abnormalities", []):
        x["started_at_offset"] += delta
        if x.get("finished_at_offset") is not None:
            x["finished_at_offset"] += delta


def _shift_existing_offsets(session: Session, hunt_id: int, delta: float) -> None:
    """Move an existing hunt's child offsets by `delta` (same alignment)."""
    for model, fields in (
        (DpsSnapshot, ("ts_offset_seconds",)),
        (MonsterHealthStep, ("ts_offset_seconds",)),
        (PlayerHealthStep, ("ts_offset_seconds",)),
        (MonsterEvent, ("start_offset_seconds", "end_offset_seconds")),
        (PlayerAbnormality, ("started_at_offset", "finished_at_offset")),
    ):
        for row in session.execute(
                select(model).where(model.hunt_id == hunt_id)).scalars():
            for f in fields:
                v = getattr(row, f)
                if v is not None:
                    setattr(row, f, v + delta)
    session.flush()


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


CROSS_SOURCE_WINDOW_SECONDS = 30
"""Tight window used when damage cannot corroborate the match (failed quests,
old mod dumps): same monster + (subset) roster starting this close is the
same hunt."""

CROSS_SOURCE_DAMAGE_WINDOW_SECONDS = 180
"""Wide start window used only when the quest also ENDS at the same time.
The mod records quest start when its script notices the quest, up to a couple
of minutes after HunterPie's timestamp (observed 78 s), so start time alone
cannot unite them."""

CROSS_SOURCE_END_WINDOW_SECONDS = 120
"""End timestamps are the reliable witness: the mod and companion both mark
the quest end, while farming repeats of the same monster minutes apart have
different ends. This prevents a later solo run from enriching an earlier
one just because its damage total is within 1%."""


def _hunt_player_names(session: Session, hunt_id: int) -> set[str]:
    rows = session.execute(
        select(Player.display_name)
        .join(HuntPlayer, HuntPlayer.player_id == Player.id)
        .where(HuntPlayer.hunt_id == hunt_id)
    ).scalars().all()
    return set(rows)


def find_hunt_by_payload(session: Session, payload: dict) -> Hunt | None:
    """Cheap pre-check: content dedup hit without touching reference rows.

    Lets callers skip ensure_monster/ensure_weapon (and their commit) for
    files that are already imported.

    Match order: (quest_id_external, monster_id, started_at) first — the
    external id is a per-SESSION hash (every quest uploaded in one gaming
    session shares it), so it only identifies a quest together with its
    start time. Still stable across renames/reorders of the same quest.
    Then the composite dedup_hash fallback. Finally a source-agnostic
    tolerant match (same monster + identical roster within a time window)
    so two tools recording the same hunt dedup.
    """
    quest_id = payload.get("quest_id_external")
    if quest_id:
        hit = session.execute(
            select(Hunt).where(Hunt.quest_id_external == quest_id,
                               Hunt.monster_id == payload["monster_id"],
                               Hunt.started_at == _coerce_ts(payload["started_at"]))
        ).scalar_one_or_none()
        if hit is not None:
            return hit
    dh = payload.get("dedup_hash")
    if not dh:
        names = sorted(p["display_name"] for p in payload.get("players", []))
        dh = compute_dedup_hash(
            payload["monster_id"], names, _coerce_ts(payload["started_at"]))
    hit = session.execute(
        select(Hunt).where(Hunt.dedup_hash == dh)
    ).scalar_one_or_none()
    if hit is not None:
        return hit

    # Tolerant cross-source match: same monster, same roster, start within
    # the window. Guards against double-counting when both the HunterPie fork
    # and the REFramework mod dump the same quest. The two sources disagree
    # on CPU support hunters (the fork lists them, the mod may not), so a
    # subset relationship also counts as the same hunt.
    players = payload.get("players") or []
    if not players:
        return None
    want = {p["display_name"] for p in players}
    started = _coerce_ts(payload["started_at"])
    incoming_end = (_coerce_ts(payload["ended_at"])
                    if payload.get("ended_at") else None)
    our_total = sum(float(p.get("total_damage", 0)) for p in players)
    lo = started - timedelta(seconds=CROSS_SOURCE_DAMAGE_WINDOW_SECONDS)
    hi = started + timedelta(seconds=CROSS_SOURCE_DAMAGE_WINDOW_SECONDS)
    candidates = session.execute(
        select(Hunt).where(Hunt.monster_id == payload["monster_id"],
                           Hunt.started_at >= lo, Hunt.started_at <= hi)
    ).scalars().all()
    for cand in candidates:
        have = _hunt_player_names(session, cand.id)
        if not (have == want or want <= have or have <= want):
            continue
        same_party_tight = abs(
            (cand.started_at - started).total_seconds()
        ) <= CROSS_SOURCE_WINDOW_SECONDS
        if same_party_tight:
            return cand
        # Wider start window is only safe when the quests also END together:
        # repeated solo hunts of the same monster can land within 1% damage.
        if incoming_end and cand.ended_at:
            end_delta = abs(
                (cand.ended_at - incoming_end).total_seconds())
            if end_delta > CROSS_SOURCE_END_WINDOW_SECONDS:
                continue
        # Wider window needs damage agreement. The mod only tracks hunters
        # it can see: unobserved roster members come in as zeros, so a
        # partial mod dump legitimately totals far less (observed 27% on an
        # 8-hunter Gog siege). Compare over mutually-observed hunters
        # instead: the same quest shows the same splits there (mod/fork
        # bias is ~1-3%), while different quests with the same roster never
        # agree hunter by hunter.
        incoming_dmg = {pl["display_name"]: float(pl.get("total_damage") or 0)
                        for pl in players}
        have_dmg = dict(session.execute(
            select(Player.display_name, HuntPlayer.total_damage)
            .join(HuntPlayer, HuntPlayer.player_id == Player.id)
            .where(HuntPlayer.hunt_id == cand.id)).all())
        common = [n for n in incoming_dmg
                  if incoming_dmg[n] > 0 and have_dmg.get(n, 0) > 0]
        if common:
            sub_in = sum(incoming_dmg[n] for n in common)
            sub_have = sum(have_dmg[n] for n in common)
            bigger = max(sub_in, sub_have)
            if sub_in > 0 and (bigger - min(sub_in, sub_have)) / bigger <= 0.03:
                if all(abs(incoming_dmg[n] - have_dmg[n])
                       / max(incoming_dmg[n], have_dmg[n]) <= 0.10
                       for n in common):
                    return cand
            continue
        # No mutually-observed damage: fall back to the whole-hunt 1%
        # check so distinct quests can't merge on zeros.
        theirs = cand.quest_damage
        if theirs and our_total > 0:
            bigger = max(theirs, our_total)
            if abs(theirs - our_total) / bigger <= 0.01:
                return cand
    return None


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


def ensure_awards(session: Session, metas: list[dict] | None) -> None:
    """Upsert award definitions (id/name/explain/unit) captured by the mod."""
    if not metas:
        return
    for m in metas:
        aid = m.get("id")
        if aid is None:
            continue
        aid = int(aid)
        row = session.get(Award, aid)
        if row is None:
            session.add(Award(
                id=aid, name=m.get("name") or f"Award {aid}",
                explain=m.get("explain"), unit=m.get("unit", 2) or 2))
        else:
            if m.get("name"):
                row.name = m["name"]
            if m.get("explain"):
                row.explain = m["explain"]
            if m.get("unit") is not None:
                row.unit = m["unit"]
    session.flush()


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
        for a in p.get("awards") or []:
            _nonneg(a.get("count", 0),
                    f"award {a.get('id')} count for {p.get('display_name')!r}")
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
    for h in payload.get("player_health", []):
        _nonneg(h.get("ts_offset_seconds"), "player_health ts_offset_seconds")
        frac = h.get("hp_fraction")
        if frac is None or not 0 <= frac <= 1:
            raise ValueError(f"player hp_fraction must be 0..1, got {frac!r}")
        red = h.get("red_fraction")
        if red is not None and not 0 <= red <= 1:
            raise ValueError(f"player red_fraction must be 0..1, got {red!r}")


def _hunt_columns(payload: dict, started_at: datetime,
                  ended_at: datetime | None, player_names: list[str]) -> dict:
    """Hunt-level columns derived from a payload (shared by create/refresh)."""
    return dict(
        quest_id_external=payload.get("quest_id_external"),
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
        # Party size = human hunters only (CPU supporters don't count). Min 1.
        player_count=max(1, sum(1 for p in payload["players"]
                                if not p.get("is_supporter"))),
        is_sos=bool(payload.get("is_sos", False)),
        joined_mid_hunt=bool(payload.get("joined_mid_hunt", False)),
        quest_damage=sum(float(p.get("total_damage", 0))
                         for p in payload["players"]),
        is_split_quest=bool(payload.get("is_split_quest", False)),
        hunterpie_version=payload["hunterpie_version"],
        game_version=payload["game_version"],
        mod_version=payload.get("mod_version"),
    )


def _add_award(session: Session, hunt_id: int, player_id: int, a: dict) -> None:
    aid = a.get("id")
    if aid is None:
        return
    ch = a.get("channels")
    count = float(a.get("count", 0) or 0)
    # Award 0 (Support All-Star) is a uint32[4] channel array; the per-hunt
    # value is the sum of its channels.
    if int(aid) == 0 and ch:
        count = float(sum(x or 0 for x in ch))
    session.add(HuntPlayerAward(
        hunt_id=hunt_id, player_id=player_id, award_id=int(aid), count=count,
        channels=json.dumps(ch) if ch else None))


def _delete_children(session: Session, hunt_id: int) -> None:
    for model in (DpsSnapshot, MonsterEvent, MonsterHealthStep,
                  PlayerAbnormality, PlayerHealthStep):
        session.execute(delete(model).where(model.hunt_id == hunt_id))
    session.execute(delete(HuntPlayer).where(HuntPlayer.hunt_id == hunt_id))


def _insert_children(session: Session, hunt: Hunt, payload: dict,
                     now: datetime, warnings: list[str], cache: dict,
                     supporter_names: set[str] | None = None,
                     weapon_names: dict[str, str] | None = None) -> None:
    """Players (+ awards), snapshots, events, HP steps and abnormalities.

    ``supporter_names`` force-flags CPU support hunters that HunterPie lists
    as ordinary players (it does not mark them; the mod does).
    ``weapon_names`` restores the mod's local-player weapon name when a
    HunterPie dump refreshes a mod-created hunt (HunterPie has no name)."""
    supporter_names = supporter_names or set()
    weapon_names = weapon_names or {}
    player_ids: dict[str, int] = {}
    for p in payload["players"]:
        pkey = ("player", p["display_name"])
        pid = cache.get(pkey)
        if pid is None:
            player = get_or_create_player(session, p["display_name"], now,
                                          warnings)
            pid = player.id
            cache[pkey] = pid
        player_ids[p["display_name"]] = pid
        gear = p.get("gear") or {}
        if gear and {"raw", "element", "affinity"} <= set(gear):
            wid = p.get("weapon_id")
            weapon = session.get(Weapon, wid) if wid is not None else None
            wtype = weapon.name if weapon else "Unknown"
            ikey = ("identity", wtype, gear["raw"], gear["element"],
                    gear["affinity"])
            if ikey not in cache:
                cache[ikey] = get_or_create_identity(session, wtype, gear).id
        else:
            gear = {}
        session.add(HuntPlayer(
            hunt_id=hunt.id, player_id=pid, weapon_id=p.get("weapon_id"),
            total_damage=p.get("total_damage", 0),
            peak_dps=p.get("peak_dps", 0),
            is_supporter=bool(p.get("is_supporter", False))
            or p["display_name"] in supporter_names,
            gear_raw=gear.get("raw"), gear_element=gear.get("element"),
            gear_affinity=gear.get("affinity"),
            weapon_name=(p.get("weapon_name")
                         or weapon_names.get(p["display_name"]))))
        for a in p.get("awards") or []:
            _add_award(session, hunt.id, pid, a)
    for s in payload.get("snapshots", []):
        if s["display_name"] not in player_ids:
            raise ValueError(
                f"snapshot references unknown player '{s['display_name']}'")
        session.add(DpsSnapshot(
            hunt_id=hunt.id, player_id=player_ids[s["display_name"]],
            ts_offset_seconds=s["ts_offset_seconds"],
            cumulative_damage=s.get("cumulative_damage", 0),
            instant_dps=s.get("instant_dps", 0)))
    for e in payload.get("events", []):
        session.add(MonsterEvent(
            hunt_id=hunt.id, monster_id=hunt.monster_id,
            event_type=e["event_type"],
            start_offset_seconds=e["start_offset_seconds"],
            end_offset_seconds=e.get("end_offset_seconds")))
    for h in payload.get("hp_steps", []):
        session.add(MonsterHealthStep(
            hunt_id=hunt.id, monster_id=hunt.monster_id,
            ts_offset_seconds=h["ts_offset_seconds"],
            hp_fraction=h["hp_fraction"]))
    for a in payload.get("abnormalities", []):
        if a["display_name"] not in player_ids:
            continue
        session.add(PlayerAbnormality(
            hunt_id=hunt.id, player_id=player_ids[a["display_name"]],
            abnormality_id=a["abnormality_id"], category=a["category"],
            started_at_offset=a["started_at_offset"],
            finished_at_offset=a.get("finished_at_offset")))
    for h in payload.get("player_health", []):
        if h.get("display_name") not in player_ids:
            continue
        session.add(PlayerHealthStep(
            hunt_id=hunt.id, player_id=player_ids[h["display_name"]],
            ts_offset_seconds=h["ts_offset_seconds"],
            hp_fraction=h["hp_fraction"],
            red_fraction=h.get("red_fraction"),
            max_hp=h.get("max_hp")))


def _refresh_from_hunterpie(session: Session, hunt: Hunt, payload: dict,
                            now: datetime, warnings: list[str],
                            cache: dict) -> None:
    """Replace a REFramework-created hunt's core with the HunterPie dump.

    The mod's per-player weapon map is unreliable and HunterPie owns damage,
    weapons and curves; its awards are left in place (keyed by hunt_id)."""
    started = _coerce_ts(payload["started_at"])
    ended = _coerce_ts(payload["ended_at"]) if payload.get("ended_at") else None
    # Keep the EARLIEST start (the mod usually sees the quest before a
    # late-launched companion) and push the incoming dump's offsets later so
    # both sources share one true timeline.
    old_started, old_ended = hunt.started_at, hunt.ended_at
    late_by = (started - old_started).total_seconds()
    if late_by > 0:
        _shift_payload_offsets(payload, late_by)
        started = old_started
        if old_ended is not None:
            ended = old_ended
        payload["quest_time_seconds"] = (
            (ended - started).total_seconds() if ended else None)
    elif late_by < 0:
        # The companion attached before the mod: keep its earlier timeline as
        # the origin and move the mod's existing samples later with it.
        _shift_existing_offsets(session, hunt.id, -late_by)
    # HunterPie lists CPU support hunters as ordinary players; keep the
    # mod's supporter flags (they drive party size and synergy).
    supporters = {name for name, sup in session.execute(
        select(Player.display_name, HuntPlayer.is_supporter)
        .select_from(HuntPlayer)
        .join(Player, Player.id == HuntPlayer.player_id)
        .where(HuntPlayer.hunt_id == hunt.id)).all() if sup}
    # HunterPie has no weapon names; keep the mod's local-player name.
    names = {name: wn for name, wn in session.execute(
        select(Player.display_name, HuntPlayer.weapon_name)
        .select_from(HuntPlayer)
        .join(Player, Player.id == HuntPlayer.player_id)
        .where(HuntPlayer.hunt_id == hunt.id)).all() if wn}
    cols = _hunt_columns(payload, started, ended,
                         sorted(p["display_name"] for p in payload["players"]))
    cols["player_count"] = max(1, sum(
        1 for p in payload["players"]
        if p["display_name"] not in supporters))
    # The companion has no mod_version; keep the last one seen for this hunt
    # so the "reinstall the mod" notice doesn't disappear on a refresh.
    if not cols.get("mod_version"):
        cols["mod_version"] = hunt.mod_version
    try:
        for key, value in cols.items():
            setattr(hunt, key, value)
        hunt.source = "hunterpie"
        # HunterPie has no player HP; keep the mod's samples across the
        # refresh (player ids are name-keyed, so they survive re-insert).
        saved_health = [(
            r.player_id, r.ts_offset_seconds, r.hp_fraction,
            r.red_fraction, r.max_hp,
        ) for r in session.execute(
            select(PlayerHealthStep)
            .where(PlayerHealthStep.hunt_id == hunt.id)).scalars().all()]
        _delete_children(session, hunt.id)
        session.flush()
        _insert_children(session, hunt, payload, now, warnings, cache,
                         supporter_names=supporters, weapon_names=names)
        for pid, ts, hp, red, mx in saved_health:
            session.add(PlayerHealthStep(
                hunt_id=hunt.id, player_id=pid, ts_offset_seconds=ts,
                hp_fraction=hp, red_fraction=red, max_hp=mx))
        session.commit()
    except Exception:
        session.rollback()
        raise


def _enrich_from_reframework(session: Session, hunt: Hunt,
                             payload: dict) -> None:
    """Apply the mod's extras to an existing HunterPie hunt.

    The mod contributes only what HunterPie lacks: the local player's weapon
    name, CPU-supporter flags, player HP samples, and the quest awards.
    Damage and weapon classes stay as HunterPie recorded them."""
    hp_by_name = {name: hp for name, hp in session.execute(
        select(Player.display_name, HuntPlayer)
        .select_from(HuntPlayer)
        .join(Player, Player.id == HuntPlayer.player_id)
        .where(HuntPlayer.hunt_id == hunt.id)).all()}
    # The companion created this hunt, possibly after a mid-hunt attach: its
    # clock is later than the mod's. Rebase everything onto the mod's earlier
    # (true) start so HP and DPS share one timeline.
    mod_start = _coerce_ts(payload["started_at"])
    lead = (hunt.started_at - mod_start).total_seconds()
    if lead > 0:
        _shift_existing_offsets(session, hunt.id, lead)
        hunt.started_at = mod_start
        if hunt.ended_at is not None:
            hunt.ended_at = hunt.ended_at - timedelta(seconds=lead)
    elif lead < 0:
        # The companion attached first: its start is the timeline origin, so
        # the mod's offsets (relative to its later start) move forward.
        _shift_payload_offsets(payload, -lead)
    have = set(session.execute(
        select(HuntPlayerAward.player_id, HuntPlayerAward.award_id)
        .where(HuntPlayerAward.hunt_id == hunt.id)).all())
    changed = False
    # A newer mod dump for a companion-created hunt updates the version we
    # report (the "reinstall the mod" notice clears after an upgrade).
    mod_version = payload.get("mod_version")
    if mod_version and hunt.mod_version != mod_version:
        hunt.mod_version = mod_version
        changed = True
    for p in payload["players"]:
        hp = hp_by_name.get(p["display_name"])
        if hp is None:
            continue
        wname = p.get("weapon_name")
        if wname and hp.weapon_name != wname:
            hp.weapon_name = wname
            changed = True
        if p.get("is_supporter") and not hp.is_supporter:
            hp.is_supporter = True
            changed = True
        for a in p.get("awards") or []:
            aid = a.get("id")
            if aid is None or (hp.player_id, int(aid)) in have:
                continue
            _add_award(session, hunt.id, hp.player_id, a)
            changed = True
    # Player HP samples are quest-wide and mod-only: replace any previous
    # attach so repeated enriches can't duplicate rows.
    mod_health = payload.get("player_health") or []
    if mod_health:
        session.execute(delete(PlayerHealthStep)
                        .where(PlayerHealthStep.hunt_id == hunt.id))
        for h in mod_health:
            hp = hp_by_name.get(h.get("display_name"))
            if hp is None:
                continue
            session.add(PlayerHealthStep(
                hunt_id=hunt.id, player_id=hp.player_id,
                ts_offset_seconds=h["ts_offset_seconds"],
                hp_fraction=h["hp_fraction"],
                red_fraction=h.get("red_fraction"),
                max_hp=h.get("max_hp")))
            changed = True
    if changed:
        hunt.player_count = max(1, sum(
            1 for hp in hp_by_name.values() if not hp.is_supporter))
        session.commit()


#: HP identity reconciliation. The mod keys HP samples by control slot
#: but names them by compact-list position; when lobby slot order differs
#: from network user order (observed on an 8-hunter Gog siege) every sample
#: lands correctly-keyed but wrongly-named, and the dump's name-first
#: assignment swaps two hunters — a faint Diego dealt showed up as Light.
#: Repair only on physical impossibility, never on heuristics alone:
#: a hunter dealing damage straight through their own 0-HP readings with
#: instant full recovery cannot be the one who fainted. The unique silent
#: hunter covering that window gets the series. Anything ambiguous only
#: warns. Re-running converges (corrected data shows no contradiction).
HP_ZERO_EPS = 0.01
HP_OWN_GAP_S = 20.0
HP_DAMAGE_NEAR_S = 20.0
HP_RECOVER_S = 20.0
HP_RECOVER_FULL = 0.9
HP_COMPLEMENT_GAP_S = 25.0
HP_PRE_DECLINE = 0.85
HP_PRE_WINDOW_S = 15.0
# A damage tick within ~3s of the first zero sample is the fainting moment
# itself (last hit dealt going down / in-flight damage on a 5s HP poll
# cadence), not proof of fighting while downed. Seen live: a final tick
# 0.1s before the zero nearly caused a false swap of a correct series.
HP_ZERO_EDGE_SLOP_S = 3.0
# The true owner's damage stops AT the faint: a swap candidate whose silence
# started long before the zero fainted earlier (or never) and cannot own
# this one. Seen live: a 47s-earlier silence falsely attracted a swap.
HP_GAP_START_SLOP_S = 10.0


def _hp_zero_runs(series):
    """Contiguous hp<=eps runs as (start, end) from a ts-ordered series."""
    runs = []
    start = None
    prev = 0.0
    for t, hp in series:
        if hp <= HP_ZERO_EPS:
            if start is None:
                start = t
            prev = t
        else:
            if start is not None:
                runs.append((start, prev))
                start = None
    if start is not None:
        runs.append((start, prev))
    return runs


def _covering_gap(ticks, t0, t1, min_len):
    """Longest snapshot gap covering [t0, t1], or None."""
    best = None
    for a, b in zip(ticks, ticks[1:]):
        if a <= t0 and b >= t1 and b - a >= min_len:
            if best is None or b - a > best[1] - best[0]:
                best = (a, b)
    return best


def reconcile_hp_identity(session, hunt):
    """Reattribute swapped player-HP series when the data proves it.

    Returns warnings (empty when nothing was wrong). Swaps whole series:
    the order mismatch poisons every sample of the hunt equally, so a
    window-only fix would leave Frankenstein series behind.
    """
    warnings = []
    hp_rows = session.execute(
        select(PlayerHealthStep.player_id,
               PlayerHealthStep.ts_offset_seconds,
               PlayerHealthStep.hp_fraction)
        .where(PlayerHealthStep.hunt_id == hunt.id)
        .order_by(PlayerHealthStep.player_id,
                   PlayerHealthStep.ts_offset_seconds)
    ).all()
    if not hp_rows:
        return warnings
    by_hp = {}
    for pid, ts, hp in hp_rows:
        by_hp.setdefault(pid, []).append((ts, hp))
    pids = sorted(by_hp)
    tick_rows = session.execute(
        select(DpsSnapshot.player_id, DpsSnapshot.ts_offset_seconds)
        .where(DpsSnapshot.hunt_id == hunt.id,
               DpsSnapshot.player_id.in_(pids))
        .order_by(DpsSnapshot.player_id,
                   DpsSnapshot.ts_offset_seconds)
    ).all()
    by_ticks = {}
    for pid, ts in tick_rows:
        by_ticks.setdefault(pid, []).append(ts)
    if not any(by_ticks.values()):
        return warnings
    names = dict(session.execute(
        select(Player.id, Player.display_name)
        .where(Player.id.in_(pids))).all())

    swaps = {}
    for pid, series in by_hp.items():
        ticks = by_ticks.get(pid, [])
        for t0, t1 in _hp_zero_runs(series):
            # Own silence must cover past the faint boundary: a final tick
            # landing within slop of the first zero is the downing moment.
            if _covering_gap(ticks, t0 + HP_ZERO_EDGE_SLOP_S, t1,
                             HP_OWN_GAP_S) is not None:
                continue  # own silence: consistent with fainting
            near = [t for t in ticks
                    if t0 - HP_DAMAGE_NEAR_S <= t <= t1 + HP_DAMAGE_NEAR_S
                    and abs(t - t0) > HP_ZERO_EDGE_SLOP_S]
            if not near:
                continue  # silent throughout: no contradiction
            rt = next((t for t, hp in series
                       if t > t1 and hp >= HP_RECOVER_FULL), None)
            if rt is None or rt - t1 > HP_RECOVER_S:
                continue  # slow/no recovery: consistent with a real faint
            pre = [hp for t, hp in series
                   if t0 - HP_PRE_WINDOW_S <= t < t0]
            if not pre or pre[-1] >= HP_PRE_DECLINE:
                # Instant 1.0->0 cliff with no taking-damage ramp: sampling
                # artifact, not someone's faint. Flag, don't reassign.
                warnings.append(
                    "hp-artifact?: %s HP hits 0 near t=%.0fs but kept "
                    "dealing damage - no pre-faint decline, left as is"
                    % (names.get(pid, pid), t0))
                continue
            cands = []
            for opid in pids:
                if opid == pid:
                    continue
                oticks = by_ticks.get(opid, [])
                g = _covering_gap(oticks, t0, t1, HP_COMPLEMENT_GAP_S)
                # Interior gap only: started before any damage, ends after.
                # Plus it must START at this zero (within slop): whoever owns
                # the faint stops dealing then. An earlier silence is their
                # own earlier faint, not this one.
                if (g is not None and oticks and oticks[0] < g[0]
                        and oticks[-1] > g[1]
                        and abs(g[0] - t0) <= HP_GAP_START_SLOP_S):
                    cands.append(opid)
            if len(cands) != 1:
                warnings.append(
                    "hp-mislabel?: %s HP hits 0 near t=%.0fs while "
                    "dealing damage (%d silent candidates) - left as is"
                    % (names.get(pid, pid), t0, len(cands)))
                continue
            swaps[pid] = cands[0]
    # Only disjoint pairs (each hunter in at most one swap); chains or
    # conflicts warn without touching anything.
    upairs = set()
    for a, b in swaps.items():
        upairs.add((min(a, b), max(a, b)))
    used = []
    for a, b in upairs:
        used.extend([a, b])
    if swaps and len(set(used)) != 2 * len(upairs):
        warnings.append("hp-mislabel?: conflicting reassignments - left as is")
        return warnings
    for a, b in sorted(upairs):
        # The zero-run sits on a's series but a kept dealing: the faint is
        # b's. Swap the two series wholesale and say so.
        zts = [t0 for t0, t1 in _hp_zero_runs(by_hp[a])]
        zt = zts[0] if zts else 0.0
        session.execute(
            update(PlayerHealthStep)
            .where(PlayerHealthStep.hunt_id == hunt.id,
                   PlayerHealthStep.player_id.in_((a, b)))
            .values(player_id=case(
                (PlayerHealthStep.player_id == a, b), else_=a)))
        warnings.append(
            "hp-identity-fixed: %s HP near t=%.0fs belongs to %s "
            "(series were swapped); reassigned"
            % (names.get(a, a), zt, names.get(b, b)))
    return warnings


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

    source = payload.get("source", "hunterpie")
    # R1: abnormalities are companion-only. A REFramework payload's buff export
    # is dropped outright so the mod can never contribute abnormality rows.
    # R2: buildup meters (Debuffs.<n>.BuildUp) are 0-100 gauges, not timed
    # windows, so they are filtered here — the single gate before storage.
    if source != "hunterpie":
        payload["abnormalities"] = []
    else:
        payload["abnormalities"] = [
            a for a in (payload.get("abnormalities") or [])
            if AbnormalityId.parse(a["abnormality_id"]).is_displayable
        ]
    # Award definitions (idempotent) must exist before ANY path can write
    # hunt_player_awards — including _enrich_from_reframework below, which
    # adds the mod's awards to a hunt a HunterPie dump created first. On a
    # fresh DB the awards table is empty there, and the FK on award_id would
    # reject every enrich (only visible with PRAGMA foreign_keys=ON, which
    # _on_connect sets for the app's engines).
    ensure_awards(session, payload.get("awards_meta"))
    existing = find_hunt_by_payload(session, payload)
    if existing is not None:
        # HunterPie owns damage/weapons/curves; the REFramework mod adds awards.
        if source == "hunterpie" and existing.source != "hunterpie":
            _refresh_from_hunterpie(session, existing, payload, now, warnings,
                                    cache)
        elif source == "reframework" and existing.source == "hunterpie":
            _enrich_from_reframework(session, existing, payload)
        warnings.extend(reconcile_hp_identity(session, existing))
        return existing, False, warnings

    try:
        hunt = Hunt(source=source,
                    **_hunt_columns(payload, started_at, ended_at, player_names))
        if hunt.is_sos or hunt.joined_mid_hunt:
            warnings.append("untrusted-flags: is_sos/joined_mid_hunt set — verify before trusting stats")
            log.debug("hunt %s has untrusted SOS/mid-join flags", quest_id)
        session.add(hunt)
        session.flush()
        # Guard against orphaned child rows for a reused rowid (a hunt id can
        # be reused after a delete outside the app's FK-cascading session).
        _delete_children(session, hunt.id)
        _insert_children(session, hunt, payload, now, warnings, cache)
        warnings.extend(reconcile_hp_identity(session, hunt))
        session.commit()
    except Exception:
        session.rollback()
        raise
    return hunt, True, warnings
