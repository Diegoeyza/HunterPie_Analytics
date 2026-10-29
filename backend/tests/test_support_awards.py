"""Support All-Star ("Buffs and Heals Applied") attribution.

The game counts a support action once per hunter it affected. HunterPie/the
mod export award 0 as a uint32[4] *row* per party member, indexed by the party
position of the hunter who applied it — a row is what that member *received*
(its diagonal is self-support). The count the game shows is therefore the
applier's *column* across the party, not their row: summing the row gave
"support received", which is why a hunting-horn hunter with ~500 applied buffs
showed ~200.
"""
from datetime import datetime, timedelta

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.awards import support_applied
from app.db import _on_connect, migrate
from app.ingest import _support_applied, upsert_hunt
from app.models import Base, HuntPlayerAward, Monster, Player, Weapon

T0 = datetime(2026, 10, 29, 16, 16, 42)


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    event.listen(engine, "connect", _on_connect)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, future=True)()
    s.add_all([Monster(id=27, name="Arkveld"),
               Weapon(id=6, name="Hunting Horn", weapon_type="HH")])
    s.commit()
    return s


# The real award-0 matrix of a 4-hunter hunt: rows are what each hunter
# received, columns are who applied it. Isi (party position 2) applied 411.
MATRIX = {
    "Malafax": [3, 0, 73, 0],
    "Tyrann": [1, 0, 72, 1],
    "Isi": [1, 0, 205, 0],
    "Smokey": [1, 0, 61, 1],
}


def _awards(channels):
    if channels is None:
        return [{"id": 4, "count": 1000}]
    return [{"id": 0, "count": sum(channels), "channels": channels},
            {"id": 4, "count": 1000}]


def _payload(source="reframework", start=T0, matrix=MATRIX):
    players = [{"display_name": name, "weapon_id": 6, "total_damage": 1000.0,
                "peak_dps": 50.0, "is_supporter": False,
                "awards": _awards(matrix.get(name))}
               for name in MATRIX]
    return {
        "quest_id_external": "q1", "monster_id": 27,
        "_monster_name": "Arkveld", "started_at": start,
        "ended_at": start + timedelta(seconds=600), "quest_time_seconds": 600,
        "cart_count": 0, "cleared": True, "hunterpie_version": "t",
        "game_version": "1.042.00.03", "source": source,
        "mod_version": "0.12.3" if source != "hunterpie" else None,
        "players": players,
        "snapshots": [{"display_name": "Isi", "ts_offset_seconds": t,
                       "cumulative_damage": 400.0, "instant_dps": 10.0}
                      for t in (30.0, 90.0)],
        "abnormalities": [], "hp_steps": [{"ts_offset_seconds": 0.0,
                                           "hp_fraction": 1.0}],
        "events": [], "player_health": [],
        "awards_meta": [{"id": 0, "name": "Support All-Star",
                         "explain": "Buffs and Heals Applied", "unit": 0},
                        {"id": 4, "name": "Established Hunter",
                         "explain": "Damage", "unit": 2}],
    }


def _support(s):
    return {name: round(count, 0) for name, count in s.execute(
        select(Player.display_name, HuntPlayerAward.count)
        .join(HuntPlayerAward, HuntPlayerAward.player_id == Player.id)
        .where(HuntPlayerAward.award_id == 0)).all()}


def test_column_sum_is_the_applied_support():
    applied = _support_applied([
        {"display_name": n, "awards": _awards(MATRIX[n])} for n in MATRIX])
    assert applied == {"Malafax": 6.0, "Tyrann": 0.0, "Isi": 411.0,
                       "Smokey": 2.0}


def test_party_slot_gap_keeps_every_hunters_support():
    """Three hunters, one of whom sat in slot 3 (a gap at slot 2): the cells
    outside the row range still belong to a hunter, so nothing is dropped."""
    rows = [[20, 4, 0, 1], [10, 8, 0, 1], [10, 4, 0, 2]]
    applied = support_applied(rows)
    assert applied == [40.0, 16.0, 4.0]
    assert sum(applied) == sum(sum(r) for r in rows)  # total preserved


def test_ingest_credits_the_applier_not_the_receiver():
    s = _session()
    upsert_hunt(s, _payload())
    assert _support(s) == {"Malafax": 6, "Tyrann": 0, "Isi": 411, "Smokey": 2}


def test_companion_hunt_gets_the_same_numbers_from_the_mod_dump():
    s = _session()
    upsert_hunt(s, _payload(source="hunterpie", start=T0 + timedelta(seconds=8)))
    upsert_hunt(s, _payload(start=T0))
    assert _support(s) == {"Malafax": 6, "Tyrann": 0, "Isi": 411, "Smokey": 2}


def test_solo_scalar_is_kept_when_the_party_has_no_channels():
    s = _session()
    payload = _payload()
    for p in payload["players"]:
        p["awards"] = [{"id": 0, "count": 37}]  # self award: no channels
    upsert_hunt(s, payload)
    assert set(_support(s).values()) == {37.0}


def test_migration_rebuilds_counts_from_stored_channels(tmp_path):
    path = str(tmp_path / "old.db")
    engine = create_engine(f"sqlite:///{path}", future=True)
    event.listen(engine, "connect", _on_connect)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, future=True)()
    s.add_all([Monster(id=27, name="Arkveld"),
               Weapon(id=6, name="Hunting Horn", weapon_type="HH")])
    s.commit()
    upsert_hunt(s, _payload())
    # Simulate the old (row-sum) numbers and an un-migrated DB.
    s.execute(HuntPlayerAward.__table__.update()
              .where(HuntPlayerAward.award_id == 0)
              .values(count=999.0))
    s.commit()
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA user_version=9")
    migrate(engine=engine)
    counts = {name: round(c, 0) for name, c in s.execute(
        select(Player.display_name, HuntPlayerAward.count)
        .join(HuntPlayerAward, HuntPlayerAward.player_id == Player.id)
        .where(HuntPlayerAward.award_id == 0)).all()}
    assert counts == {"Malafax": 6, "Tyrann": 0, "Isi": 411, "Smokey": 2}
