"""Quest clock: the companion starts on the loading screen, the mod in-quest.

The fork keeps sampling from quest *accept*, so its timeline runs ~6-25s
early (observed median 11.5s across 194 paired dumps). Every offset on a
companion-created hunt was therefore measured from the loading screen, which
put pre-quest buffs at the left edge of the Buffs timeline and inflated the
reported clear time. The mod's first in-quest sample is the real start.

Guard: the companion's earlier clock is only dropped when the mod's own data
proves it saw the quest from the start (monster at full HP on its first HP
step). A mod that attached mid-fight leaves the companion clock alone.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db import _on_connect
from app.ingest import upsert_hunt
from app.models import (
    Base,
    DpsSnapshot,
    Hunt,
    Monster,
    PlayerAbnormality,
    PlayerHealthStep,
    Weapon,
)

T0 = datetime(2026, 10, 26, 19, 27, 33)
LEAD = 12.0        # companion leads the mod by 12s


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    event.listen(engine, "connect", _on_connect)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, future=True)()
    s.add(Monster(id=1, name="Xu Wu"))
    s.add(Weapon(id=1, name="Great Sword", weapon_type="GS"))
    s.commit()
    return s


def _companion(start=T0, span=300.0):
    """A HunterPie fork dump: begins on the loading screen."""
    return {
        "quest_id_external": "q1", "monster_id": 1, "_monster_name": "Xu Wu",
        "started_at": start, "ended_at": start + timedelta(seconds=span),
        "quest_time_seconds": span, "cart_count": 0, "cleared": True,
        "hunterpie_version": "t", "game_version": "g", "source": "hunterpie",
        "players": [{"display_name": "Isi", "weapon_id": 1,
                     "total_damage": 1000.0, "peak_dps": 50.0,
                     "is_supporter": False}],
        # Damage only after the quest really starts (companion offset 18s = 6s
        # in-quest), so nothing legitimate sits before t=0 after the shift.
        "snapshots": [{"display_name": "Isi", "ts_offset_seconds": float(t),
                       "cumulative_damage": 1000.0 * t / span,
                       "instant_dps": 10.0}
                      for t in range(18, int(span) + 1, 10)],
        "abnormalities": [
            # Loading-screen junk (0.1s item-use blip), as seen live.
            {"display_name": "Isi", "abnormality_id": "Consumables_Consumables.7C",
             "category": "Consumables", "started_at_offset": 2.0,
             "finished_at_offset": 2.1},
            # Straddles the real start: active before, still active after.
            {"display_name": "Isi", "abnormality_id": "Consumables_Consumables.88",
             "category": "Consumables", "started_at_offset": 10.0,
             "finished_at_offset": 60.0},
            # Fully inside the quest.
            {"display_name": "Isi", "abnormality_id": "Skills_Skills.115",
             "category": "Skills", "started_at_offset": 40.0,
             "finished_at_offset": 90.0},
        ],
        "hp_steps": [],
        "events": [],
        "player_health": [],
    }


def _mod(start=T0 + timedelta(seconds=LEAD), span=300.0, first_hp=1.0):
    """A REFramework dump: starts in-quest, first monster HP step at t=0."""
    return {
        "quest_id_external": "q1", "monster_id": 1, "_monster_name": "Xu Wu",
        "started_at": start, "ended_at": start + timedelta(seconds=span),
        "quest_time_seconds": span, "cart_count": 0, "cleared": True,
        "hunterpie_version": "t", "game_version": "g",
        "source": "reframework", "mod_version": "0.12.3",
        "players": [{"display_name": "Isi", "weapon_id": 1,
                     "total_damage": 1000.0, "peak_dps": 50.0,
                     "is_supporter": False, "weapon_name": "Great Sword",
                     "awards": []}],
        "snapshots": [], "abnormalities": [], "events": [],
        "hp_steps": [{"ts_offset_seconds": 0.0, "hp_fraction": first_hp},
                     {"ts_offset_seconds": 5.0,
                      "hp_fraction": max(0.0, first_hp - 0.02)}],
        "player_health": [{"display_name": "Isi", "ts_offset_seconds": 0.5,
                           "hp_fraction": 1.0, "red_fraction": 0.0,
                           "max_hp": 150.0}],
    }


def _abnormalities(s, hunt_id):
    return [(r.started_at_offset, r.finished_at_offset) for r in session_scalars(
        s, select(PlayerAbnormality)
        .where(PlayerAbnormality.hunt_id == hunt_id)
        .order_by(PlayerAbnormality.started_at_offset))]


def session_scalars(s, stmt):
    return s.execute(stmt).scalars().all()


def _offsets(s, model, hunt_id):
    return [r.ts_offset_seconds for r in session_scalars(
        s, select(model).where(model.hunt_id == hunt_id)
        .order_by(model.ts_offset_seconds))]


def test_loading_lead_dropped_when_mod_enriches():
    """Companion first, mod second: rebase onto the mod's in-quest start."""
    s = _session()
    companion = _companion()
    hunt, created, _ = upsert_hunt(s, companion)
    assert created and hunt.started_at == T0
    assert hunt.quest_time_seconds == pytest.approx(300.0)

    upsert_hunt(s, _mod())
    s.expire_all()
    hunt = s.execute(select(Hunt)).scalar_one()

    assert hunt.started_at == T0 + timedelta(seconds=LEAD)
    assert hunt.ended_at == T0 + timedelta(seconds=300)
    assert hunt.quest_time_seconds == pytest.approx(300.0 - LEAD)
    # Loading-screen blip gone, straddling window clamped to the quest start.
    assert _abnormalities(s, hunt.id) == [(0.0, 48.0), (28.0, 78.0)]
    # Companion damage moves with the clock and nothing survives before t=0.
    snaps = _offsets(s, DpsSnapshot, hunt.id)
    assert snaps[0] == pytest.approx(18.0 - LEAD)
    assert all(t >= 0 for t in snaps)
    # The mod's own samples are already quest-relative: untouched.
    assert _offsets(s, PlayerHealthStep, hunt.id)[0] == pytest.approx(0.5)


def test_loading_lead_dropped_when_companion_refreshes_mod_hunt():
    """Mod first, companion second: same result, no double rebase."""
    s = _session()
    hunt, created, _ = upsert_hunt(s, _mod())
    assert created and hunt.started_at == T0 + timedelta(seconds=LEAD)

    upsert_hunt(s, _companion())
    s.expire_all()
    hunt = s.execute(select(Hunt)).scalar_one()

    assert hunt.started_at == T0 + timedelta(seconds=LEAD)
    assert hunt.ended_at == T0 + timedelta(seconds=300)
    assert hunt.quest_time_seconds == pytest.approx(300.0 - LEAD)
    assert hunt.source == "hunterpie"
    assert _abnormalities(s, hunt.id) == [(0.0, 48.0), (28.0, 78.0)]
    assert _offsets(s, PlayerHealthStep, hunt.id)[0] == pytest.approx(0.5)


def test_mid_fight_mod_attach_keeps_companion_clock():
    """Mod has the monster already hurt: it attached late, not the companion."""
    s = _session()
    upsert_hunt(s, _companion())
    mod = _mod(start=T0 + timedelta(seconds=40), first_hp=0.80)

    upsert_hunt(s, mod)
    s.expire_all()
    hunt = s.execute(select(Hunt)).scalar_one()

    assert hunt.started_at == T0
    assert hunt.quest_time_seconds == pytest.approx(300.0)
    # No clipping: the loading-screen windows stay put.
    assert len(_abnormalities(s, hunt.id)) == 3
    # The mod's samples moved forward onto the companion timeline.
    assert _offsets(s, PlayerHealthStep, hunt.id)[0] == pytest.approx(40.5)


def test_large_gap_is_not_treated_as_loading():
    """Beyond the loading-screen cap the companion clock stays the origin."""
    s = _session()
    upsert_hunt(s, _companion())
    upsert_hunt(s, _mod(start=T0 + timedelta(seconds=90)))

    s.expire_all()
    hunt = s.execute(select(Hunt)).scalar_one()
    assert hunt.started_at == T0
    assert hunt.quest_time_seconds == pytest.approx(300.0)


def test_split_quest_sibling_follows_the_corrected_clock():
    """A bystander monster with no mod payload of its own moves with its twin."""
    s = _session()
    s.add(Monster(id=2, name="Bystander"))
    s.commit()
    # Companion dump: one hunt per monster, same quest clock.
    for mid in (1, 2):
        payload = _companion()
        payload.update(monster_id=mid, is_split_quest=True)
        upsert_hunt(s, payload)
    hunts = s.execute(select(Hunt).order_by(Hunt.monster_id)).scalars().all()
    assert [h.started_at for h in hunts] == [T0, T0]

    # The mod dump only carries the target monster (monster 1 here).
    upsert_hunt(s, _mod())
    s.expire_all()
    hunts = s.execute(select(Hunt).order_by(Hunt.monster_id)).scalars().all()

    assert [h.started_at for h in hunts] == [T0 + timedelta(seconds=LEAD)] * 2
    assert [h.quest_time_seconds for h in hunts] == [pytest.approx(300 - LEAD)] * 2
    for h in hunts:
        assert min(a for a, _ in _abnormalities(s, h.id)) >= 0.0


def test_reimport_is_idempotent():
    """Re-importing the same mod dump must not shift the hunt again."""
    s = _session()
    upsert_hunt(s, _companion())
    upsert_hunt(s, _mod())
    s.expire_all()
    first = s.execute(select(Hunt)).scalar_one()
    before = (first.started_at, first.quest_time_seconds,
              _abnormalities(s, first.id))

    upsert_hunt(s, _mod())
    s.expire_all()
    hunt = s.execute(select(Hunt)).scalar_one()
    assert (hunt.started_at, hunt.quest_time_seconds,
            _abnormalities(s, hunt.id)) == before
