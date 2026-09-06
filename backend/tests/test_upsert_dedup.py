from datetime import datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.ingest import find_rename_candidates, upsert_hunt
from app.models import Base, DpsSnapshot, Hunt, HuntPlayer, Monster, Weapon


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
        "players": [{"display_name": "Diego", "weapon_id": 1, "total_damage": 9000, "peak_dps": 120}],
        "snapshots": [
            {"display_name": "Diego", "ts_offset_seconds": 300,
             "cumulative_damage": 4500, "instant_dps": 100}
        ],
        "events": [{"event_type": "enrage", "start_offset_seconds": 200,
                    "end_offset_seconds": 300}],
        "hunterpie_version": "2.14.0",
        "game_version": "1.40.0.0",
    }
    p.update(over)
    return p


def test_create_hunt_with_children(session):
    hunt, created, _ = upsert_hunt(session, base_payload(quest_id_external="q-1"))
    assert created and hunt.id is not None
    assert session.execute(select(Hunt)).scalar_one().id == hunt.id
    assert len(session.execute(select(HuntPlayer)).scalars().all()) == 1
    assert len(session.execute(select(DpsSnapshot)).scalars().all()) == 1


def test_idempotent_retry_same_quest_id(session):
    h1, c1, _ = upsert_hunt(session, base_payload(quest_id_external="q-1"))
    h2, c2, _ = upsert_hunt(session, base_payload(quest_id_external="q-1"))
    assert c1 is True and c2 is False
    assert h1.id == h2.id
    assert len(session.execute(select(Hunt)).scalars().all()) == 1


def test_dedup_hash_fallback_without_external_id(session):
    h1, c1, _ = upsert_hunt(session, base_payload())
    h2, c2, _ = upsert_hunt(session, base_payload())
    assert (c1, c2) == (True, False)
    assert h1.id == h2.id


def test_rename_flagged_not_merged(session):
    upsert_hunt(session, base_payload(quest_id_external="q-1"))
    _, _, warnings = upsert_hunt(session, base_payload(quest_id_external="q-2"))
    assert warnings == []  # exact same name: no warning
    _, _, warnings = upsert_hunt(
        session, base_payload(
            quest_id_external="q-3",
            players=[{"display_name": "diego", "weapon_id": 1}],
            snapshots=[],
            events=[],
        )
    )
    assert any("rename-review" in w for w in warnings)
    assert len(find_rename_candidates(session, "DIEGO")) == 2  # flag path still works
    from app.models import Player as _Player

    names = sorted(p.display_name for p in session.execute(select(_Player)).scalars())
    assert names == ["Diego", "diego"]  # flagged, never merged


def test_missing_fields_rejected_and_nothing_persisted(session):
    with pytest.raises(ValueError):
        upsert_hunt(session, {"monster_id": 1})
    assert session.execute(select(Hunt)).scalars().all() == []


def test_sos_flag_warns(session):
    _, _, warnings = upsert_hunt(
        session, base_payload(quest_id_external="q-sos", is_sos=True, joined_mid_hunt=True)
    )
    assert any("untrusted-flags" in w for w in warnings)
