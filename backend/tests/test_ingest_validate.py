"""Ingest robustness: payload validation, external-id dedup, alias review."""
from datetime import datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.ingest import find_hunt_by_payload, upsert_hunt
from app.models import Base, Hunt, Monster, PlayerAlias, Weapon


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, future=True)()
    s.add(Monster(name="Rathalos", species="Flying Wyvern"))
    s.add(Weapon(name="Great Sword", weapon_type="GS"))
    s.commit()
    yield s
    s.close()


def base_payload(**over):
    p = {
        "monster_id": 1,
        "started_at": datetime(2026, 2, 1, 12, 0, 0),
        "ended_at": datetime(2026, 2, 1, 12, 10, 0),
        "quest_time_seconds": 600,
        "real_hunt_time_seconds": 580,
        "cleared": True,
        "players": [{"display_name": "Diego", "weapon_id": 1,
                     "total_damage": 9000, "peak_dps": 120}],
        "snapshots": [
            {"display_name": "Diego", "ts_offset_seconds": 300,
             "cumulative_damage": 4500, "instant_dps": 100}
        ],
        "events": [{"event_type": "enrage", "start_offset_seconds": 200,
                    "end_offset_seconds": 300}],
        "hp_steps": [{"ts_offset_seconds": 100, "hp_fraction": 0.8}],
        "hunterpie_version": "2.14.0",
        "game_version": "1.40.0.0",
    }
    p.update(over)
    return p


def test_negative_damage_rejected_clean(session):
    bad = base_payload(quest_id_external="neg")
    bad["players"][0]["total_damage"] = -5
    with pytest.raises(ValueError, match="total_damage"):
        upsert_hunt(session, bad)
    assert session.execute(select(Hunt)).scalars().all() == []


def test_negative_snapshot_ts_rejected(session):
    bad = base_payload(quest_id_external="negts")
    bad["snapshots"][0]["ts_offset_seconds"] = -1.0
    with pytest.raises(ValueError, match="ts_offset_seconds"):
        upsert_hunt(session, bad)


def test_ended_before_started_rejected(session):
    bad = base_payload(quest_id_external="backwards",
                       ended_at=datetime(2026, 2, 1, 11, 0, 0))
    with pytest.raises(ValueError, match="precede"):
        upsert_hunt(session, bad)


def test_hp_fraction_out_of_range_rejected(session):
    bad = base_payload(quest_id_external="badhp")
    bad["hp_steps"] = [{"ts_offset_seconds": 1.0, "hp_fraction": 1.5}]
    with pytest.raises(ValueError, match="hp_fraction"):
        upsert_hunt(session, bad)


def test_event_end_before_start_rejected(session):
    bad = base_payload(quest_id_external="badev")
    bad["events"] = [{"event_type": "enrage", "start_offset_seconds": 300,
                      "end_offset_seconds": 100}]
    with pytest.raises(ValueError, match="end precedes start"):
        upsert_hunt(session, bad)


def test_external_id_dedup_survives_rename(session):
    """Same quest_id_external + monster, different player names = dupe."""
    h1, c1, _ = upsert_hunt(session, base_payload(quest_id_external="same-q"))
    alt = base_payload(quest_id_external="same-q",
                       started_at=datetime(2026, 2, 1, 12, 0, 5))
    alt["players"] = [{"display_name": "DiegoRenamed", "weapon_id": 1,
                       "total_damage": 9000, "peak_dps": 120}]
    alt["snapshots"] = []
    h2, c2, _ = upsert_hunt(session, alt)
    assert (c1, c2) == (True, False)
    assert h1.id == h2.id
    assert find_hunt_by_payload(session, alt).id == h1.id


def test_rename_records_alias_without_merging(session):
    upsert_hunt(session, base_payload(quest_id_external="q-1"))
    alt = base_payload(quest_id_external="q-2")
    alt["players"] = [{"display_name": "DIEGO", "weapon_id": 1,
                       "total_damage": 100, "peak_dps": 10}]
    alt["snapshots"] = []
    _, _, warnings = upsert_hunt(session, alt)
    assert any("rename-review" in w for w in warnings)
    row = session.execute(
        select(PlayerAlias).where(PlayerAlias.alias == "DIEGO")
    ).scalar_one_or_none()
    assert row is not None
    # exact-name re-import does not duplicate the alias row
    _, _, _ = upsert_hunt(session, base_payload(quest_id_external="q-3"))
    assert len(session.execute(select(PlayerAlias)).scalars().all()) == 1


def test_quest_damage_and_split_flag_stored(session):
    p = base_payload(quest_id_external="split-q", is_split_quest=True)
    hunt, created, _ = upsert_hunt(session, p)
    assert created
    assert hunt.quest_damage == 9000
    assert hunt.is_split_quest is True
    solo, _, _ = upsert_hunt(session, base_payload(
        quest_id_external="solo-q",
        started_at=datetime(2026, 2, 2, 12, 0, 0),
        ended_at=datetime(2026, 2, 2, 12, 10, 0)))
    assert solo.quest_damage == 9000
    assert solo.is_split_quest is False
