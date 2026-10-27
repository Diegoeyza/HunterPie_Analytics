"""Carried-in buffs: HunterPie exports an already-active buff as sub-second
glimpses at quest load, then the real window once the game applies it. A long
quest-start sequence (first hunt after a patch) can delay that by a minute, so
a Demondrug drunk before the quest showed up mid-fight.

The merge folds the opening glimpses into the first real window; mid-quest
re-drinks are left alone, and re-importing a companion dump re-applies its
buffs (that is how hunts imported before this fix are healed).
"""
from datetime import datetime, timedelta

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db import _on_connect
from app.ingest import _merge_carry_in_buffs, upsert_hunt
from app.models import Base, Monster, PlayerAbnormality, Weapon

T0 = datetime(2026, 10, 27, 15, 53, 49)


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    event.listen(engine, "connect", _on_connect)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, future=True)()
    s.add_all([Monster(id=3, name="Gravios"),
               Weapon(id=6, name="Hunting Horn", weapon_type="HH")])
    s.commit()
    return s


def _window(start, end, ab="Consumables_Consumables.88", name="Isi"):
    return {"display_name": name, "abnormality_id": ab,
            "category": "Consumables", "started_at_offset": start,
            "finished_at_offset": end}


def _payload(start=T0, windows=None, dmg_start=60.3, span=101.7, source="hunterpie"):
    return {
        "quest_id_external": "q1", "monster_id": 3, "_monster_name": "Gravios",
        "started_at": start, "ended_at": start + timedelta(seconds=span),
        "quest_time_seconds": span, "cart_count": 0, "cleared": True,
        "hunterpie_version": "t", "game_version": "1.042.00.03",
        "source": source, "mod_version": "0.12.3" if source != "hunterpie" else None,
        "players": [{"display_name": "Isi", "weapon_id": 6,
                     "total_damage": 1000.0, "peak_dps": 50.0,
                     "is_supporter": False, "awards": []}],
        "snapshots": [{"display_name": "Isi", "ts_offset_seconds": t,
                       "cumulative_damage": 400.0, "instant_dps": 10.0}
                      for t in (dmg_start, dmg_start + 50.0)],
        "abnormalities": windows if windows is not None else [],
        "hp_steps": [{"ts_offset_seconds": 0.0, "hp_fraction": 1.0}],
        "events": [], "player_health": [],
    }


def _buffs(s):
    return [(round(r.started_at_offset, 2),
             None if r.finished_at_offset is None else round(r.finished_at_offset, 2))
            for r in s.execute(select(PlayerAbnormality)
                              .order_by(PlayerAbnormality.started_at_offset)).scalars()]


def test_merge_folds_glimpses_into_the_first_real_window():
    glimpse = _window(-0.37, -0.26)   # at quest load (0.11 s)
    real = _window(55.8, 111.26)      # applied once the start sequence ended
    merged = _merge_carry_in_buffs([real, glimpse])
    assert len(merged) == 1
    assert merged[0]["started_at_offset"] == 0.0
    assert merged[0]["finished_at_offset"] == 111.26
    # The input is left as exported: a re-import must see the same dump.
    assert real["started_at_offset"] == 55.8
    assert len(_merge_carry_in_buffs([real, glimpse])) == 1


def test_mid_quest_redrink_is_not_merged():
    windows = [
        _window(-0.4, -0.3),          # carried-in glimpse
        _window(4.3, 300.0),          # buff was active from the start
        _window(400.7, 400.8),        # second drink: glimpse
        _window(411.2, 480.0),        # ...and its window, mid-fight
    ]
    merged = _merge_carry_in_buffs(windows)
    starts = [round(w["started_at_offset"], 1) for w in merged]
    assert starts == [0.0, 400.7, 411.2]
    assert merged[0]["finished_at_offset"] == 300.0


def test_window_without_glimpses_is_untouched():
    windows = [_window(21.0, 500.0), _window(511.2, 580.0)]
    assert _merge_carry_in_buffs(windows) == windows


def test_reimport_heals_a_carried_buff_after_the_clock_shift():
    """#1075: the Demondrug showed 56 s in; a re-import brings it back to 0 s."""
    s = _session()
    companion = _payload(T0, windows=[_window(63.8, 119.26), _window(7.63, 7.74)])
    upsert_hunt(s, companion)
    # The mod dump arrives 8 s later and re-anchors the hunt to the quest start:
    # the merged window moves back with it and clamps to the quest start.
    upsert_hunt(s, _payload(T0 + timedelta(seconds=8), windows=[],
                            source="reframework", span=141.0))
    s.expire_all()
    assert _buffs(s) == [(0.0, 111.26)]

    # Data imported before the merge existed kept only the late window; a
    # re-import of the companion dump re-reads the glimpse and heals it.
    s.execute(PlayerAbnormality.__table__.update().values(started_at_offset=55.8))
    s.commit()
    upsert_hunt(s, companion)
    s.expire_all()
    assert _buffs(s) == [(0.0, 111.26)]


def test_reimport_replaces_corrupt_buff_rows():
    s = _session()
    companion = _payload(T0, windows=[_window(63.8, 119.26), _window(7.63, 7.74)])
    upsert_hunt(s, companion)
    s.execute(PlayerAbnormality.__table__.update().values(started_at_offset=99.0))
    s.commit()
    upsert_hunt(s, companion)
    assert _buffs(s) == [(7.63, 119.26)]   # re-read from the dump, merged


def test_new_import_merges_before_clipping():
    s = _session()
    upsert_hunt(s, _payload(T0, windows=[_window(55.8, 111.26), _window(-0.37, -0.26)]))
    assert _buffs(s) == [(0.0, 111.26)]
