from datetime import datetime

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from app.db import _on_connect
from app.ingest import find_rename_candidates, upsert_hunt
from app.models import (
    Base,
    DpsSnapshot,
    Hunt,
    HuntPlayer,
    HuntPlayerAward,
    Monster,
    Player,
    Weapon,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    # Same PRAGMAs as the app's engines — above all foreign_keys=ON, without
    # which FK violations (e.g. award rows written before their definitions)
    # stay invisible here while breaking the real app.
    event.listen(engine, "connect", _on_connect)
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


def test_same_session_repeat_quests_coexist(session):
    """The external id is a per-session hash shared by every quest in a
    gaming session: same (external, monster) with a different start is a
    NEW hunt, not a duplicate (regression: the external-first match
    dropped farmed repeats of the same quest)."""
    h1, c1, _ = upsert_hunt(session, base_payload(quest_id_external="sess-1"))
    h2, c2, _ = upsert_hunt(session, base_payload(
        quest_id_external="sess-1",
        started_at=datetime(2026, 2, 1, 12, 30, 0),
        ended_at=datetime(2026, 2, 1, 12, 40, 0),
    ))
    assert (c1, c2) == (True, True)
    assert h1.id != h2.id
    assert len(session.execute(select(Hunt)).scalars().all()) == 2


def test_same_quest_rename_stays_dupe(session):
    """Same external id + same start with a renamed roster is still the
    same quest (the reason the external check exists)."""
    h1, c1, _ = upsert_hunt(session, base_payload(quest_id_external="sess-1"))
    h2, c2, _ = upsert_hunt(session, base_payload(
        quest_id_external="sess-1",
        players=[{"display_name": "DIEGO", "weapon_id": 1,
                  "total_damage": 9000, "peak_dps": 120}],
        snapshots=[],
    ))
    assert (c1, c2) == (True, False)
    assert h1.id == h2.id


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


def test_cross_source_same_hunt_dedups(session):
    """HunterPie fork and the REFramework mod dump the same quest with
    different external ids and a few seconds off -> one hunt, not two."""
    h1, c1, _ = upsert_hunt(session, base_payload(
        quest_id_external="pie-hash",
        started_at=datetime(2026, 2, 1, 12, 0, 3)))
    h2, c2, _ = upsert_hunt(session, base_payload(
        quest_id_external="rf-hash",
        started_at=datetime(2026, 2, 1, 12, 0, 7)))
    assert (c1, c2) == (True, False)
    assert h1.id == h2.id
    assert len(session.execute(select(Hunt)).scalars().all()) == 1


def test_cross_source_far_apart_coexist(session):
    """Outside the window they are separate hunts (farming repeats)."""
    h1, c1, _ = upsert_hunt(session, base_payload(
        quest_id_external="pie-hash",
        started_at=datetime(2026, 2, 1, 12, 0, 3)))
    h2, c2, _ = upsert_hunt(session, base_payload(
        quest_id_external="rf-hash",
        started_at=datetime(2026, 2, 1, 12, 30, 0),
        ended_at=datetime(2026, 2, 1, 12, 40, 0)))
    assert (c1, c2) == (True, True)
    assert h1.id != h2.id


def test_cross_source_repeat_solo_hunts_coexist(session):
    """Farming repeats of the same monster must not merge just because their
    damage totals happen to be within 1%. Even inside the wide start window,
    different end timestamps mean different quests."""
    h1, c1, _ = upsert_hunt(session, base_payload(
        quest_id_external="pie-early",
        started_at=datetime(2026, 2, 1, 12, 0, 0),
        ended_at=datetime(2026, 2, 1, 12, 1, 40)))
    h2, c2, _ = upsert_hunt(session, base_payload(
        quest_id_external="rf-late",
        started_at=datetime(2026, 2, 1, 12, 2, 30),
        ended_at=datetime(2026, 2, 1, 12, 4, 10),
        players=[{"display_name": "Diego", "weapon_id": 1,
                  "total_damage": 9030, "peak_dps": 120}]))
    assert (c1, c2) == (True, True)
    assert h1.id != h2.id


def test_cross_source_different_roster_coexist(session):
    """Same monster + same window but a different roster is a different hunt."""
    h1, c1, _ = upsert_hunt(session, base_payload(quest_id_external="pie-hash"))
    h2, c2, _ = upsert_hunt(session, base_payload(
        quest_id_external="rf-hash",
        players=[{"display_name": "Someone Else", "weapon_id": 1,
                  "total_damage": 9000, "peak_dps": 120}],
        snapshots=[],
        events=[],
    ))
    assert (c1, c2) == (True, True)
    assert h1.id != h2.id


_RF_AWARDS_META = [{"id": 4, "name": "Established Hunter", "unit": 0}]


def _rf_award():
    return [{"id": 4, "count": 9000}]


def test_hunterpie_dump_refreshes_reframework_hunt(session):
    """The mod's per-player weapons are unreliable, so when HunterPie's dump
    for the same hunt arrives later it overwrites the core (weapons/curves)
    and the mod's awards are kept."""
    h1, c1, _ = upsert_hunt(session, base_payload(
        quest_id_external="rf-1", source="reframework",
        awards_meta=_RF_AWARDS_META, mod_version="0.10.0",
        players=[{"display_name": "Diego", "weapon_id": None,
                  "total_damage": 9000, "peak_dps": 120,
                  "weapon_name": "Onyx Choros", "awards": _rf_award()},
                 {"display_name": "Fabius", "weapon_id": None,
                  "total_damage": 500, "peak_dps": 10, "is_supporter": True}],
        snapshots=[], events=[]))
    assert c1 is True
    h2, c2, _ = upsert_hunt(session, base_payload(
        quest_id_external="pie-1",
        started_at=datetime(2026, 2, 1, 12, 0, 5),
        ended_at=datetime(2026, 2, 1, 12, 10, 5),
        players=[{"display_name": "Diego", "weapon_id": 1,
                  "total_damage": 9000, "peak_dps": 120},
                 {"display_name": "Fabius", "weapon_id": 1,
                  "total_damage": 500, "peak_dps": 10}]))
    assert c2 is False and h1.id == h2.id
    row = session.get(Hunt, h1.id)
    assert row.source == "hunterpie"
    # Weapons come from HunterPie; the mod's CPU-supporter flag is preserved.
    fabius = session.execute(
        select(HuntPlayer).join(Player)
        .where(Player.display_name == "Fabius")).scalar_one()
    assert fabius.weapon_id == 1 and fabius.is_supporter is True
    # HunterPie has no weapon names, so the mod's local-player name survives.
    diego = session.execute(
        select(HuntPlayer).join(Player)
        .where(Player.display_name == "Diego")).scalar_one()
    assert diego.weapon_name == "Onyx Choros"
    assert row.player_count == 1
    # The companion has no mod_version: the one from the mod dump survives
    # the refresh (it powers the "reinstall the mod" notice).
    assert row.mod_version == "0.10.0"
    assert session.execute(select(func.count()).select_from(HuntPlayerAward)
                           ).scalar_one() == 1


def test_reframework_dump_enriches_hunterpie_hunt(session):
    """If HunterPie's hunt exists first, the mod contributes only what
    HunterPie lacks (weapon name, supporter flag, awards) — never weapons."""
    h1, c1, _ = upsert_hunt(session, base_payload(quest_id_external="pie-1"))
    assert c1 is True
    h2, c2, _ = upsert_hunt(session, base_payload(
        quest_id_external="rf-1", source="reframework",
        awards_meta=_RF_AWARDS_META, mod_version="0.11.0",
        started_at=datetime(2026, 2, 1, 12, 0, 5),
        ended_at=datetime(2026, 2, 1, 12, 10, 5),
        players=[{"display_name": "Diego", "weapon_id": None,
                  "total_damage": 9000, "peak_dps": 120,
                  "weapon_name": "Onyx Choros", "awards": _rf_award()}],
        snapshots=[], events=[]))
    assert c2 is False and h1.id == h2.id
    hp = session.execute(select(HuntPlayer)).scalar_one()
    assert hp.weapon_id == 1              # HunterPie's weapon class, untouched
    assert hp.weapon_name == "Onyx Choros"  # added by the mod
    assert session.get(Hunt, h1.id).source == "hunterpie"
    assert session.get(Hunt, h1.id).mod_version == "0.11.0"
    assert session.execute(select(func.count()).select_from(HuntPlayerAward)
                           ).scalar_one() == 1


def test_cross_source_subset_roster_dedup(session):
    """The two sources disagree on CPU support hunters: the fork lists them,
    the mod may not. A subset roster in the same window is the same hunt."""
    h1, c1, _ = upsert_hunt(session, base_payload(
        quest_id_external="rf-hash",
        players=[{"display_name": "Diego", "weapon_id": 1,
                  "total_damage": 9000, "peak_dps": 120}]))
    h2, c2, _ = upsert_hunt(session, base_payload(
        quest_id_external="pie-hash",
        players=[{"display_name": "Diego", "weapon_id": 1,
                  "total_damage": 9000, "peak_dps": 120},
                 {"display_name": "Fabius", "weapon_id": 1,
                  "is_supporter": True, "total_damage": 500, "peak_dps": 10}]))
    assert (c1, c2) == (True, False)
    assert h1.id == h2.id
    assert len(session.execute(select(Hunt)).scalars().all()) == 1


def test_cross_source_partial_mod_damage_merges(session):
    """Gog-siege shape: the mod tracks only hunters it sees, zero-filling
    the rest (27% whole-total gap). Past the tight start window, the match
    compares mutually-observed hunters instead of whole totals."""
    h1, c1, _ = upsert_hunt(session, base_payload(
        quest_id_external="pie-gog",
        players=[{"display_name": "Diego", "weapon_id": 1,
                  "total_damage": 74216, "peak_dps": 120},
                 {"display_name": "Fabius", "weapon_id": 1,
                  "total_damage": 23808, "peak_dps": 40}],
        snapshots=[], events=[]))
    h2, c2, _ = upsert_hunt(session, base_payload(
        quest_id_external="rf-gog", source="reframework",
        awards_meta=_RF_AWARDS_META,
        started_at=datetime(2026, 2, 1, 12, 0, 42),
        ended_at=datetime(2026, 2, 1, 12, 11, 50),
        players=[{"display_name": "Diego", "weapon_id": None,
                  "total_damage": 76273, "peak_dps": 120},
                 {"display_name": "Fabius", "weapon_id": None,
                  "total_damage": 0, "peak_dps": 0}],
        snapshots=[], events=[]))
    assert (c1, c2) == (True, False)
    assert h1.id == h2.id
    assert len(session.execute(select(Hunt)).scalars().all()) == 1


def test_cross_source_same_roster_wildly_different_damage_coexists(session):
    """Same roster inside the wide window but genuinely different damage is
    a different hunt (farming repeat), not a partial observation."""
    h1, c1, _ = upsert_hunt(session, base_payload(quest_id_external="pie-a"))
    h2, c2, _ = upsert_hunt(session, base_payload(
        quest_id_external="rf-b", source="reframework",
        awards_meta=_RF_AWARDS_META,
        started_at=datetime(2026, 2, 1, 12, 0, 42),
        ended_at=datetime(2026, 2, 1, 12, 11, 50),
        players=[{"display_name": "Diego", "weapon_id": None,
                  "total_damage": 13500, "peak_dps": 120}],
        snapshots=[], events=[]))
    assert (c1, c2) == (True, True)
    assert h1.id != h2.id
