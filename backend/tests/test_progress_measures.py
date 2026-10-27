"""Progress measures: raw DPS is noisy, so the endpoint also carries the
party damage share and a monster-relative index (100% = your own median DPS
on that monster). Both are computed server-side: the share needs the party's
damage even when the hunter filter hides the other players.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db import _on_connect
from app.ingest import upsert_hunt
from app.models import Base, Monster, Player, Weapon
from app.queries import progress

T0 = datetime(2026, 10, 1, 20, 0, 0)


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    event.listen(engine, "connect", _on_connect)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, future=True)()
    s.add_all([Monster(id=31, name="Xu Wu"), Monster(id=32, name="Arkveld"),
               Weapon(id=6, name="Hunting Horn", weapon_type="HH")])
    s.commit()
    return s


def _payload(index: int, damage: dict[str, float], monster_id: int = 31):
    start = T0 + timedelta(hours=index)
    return {
        "quest_id_external": f"q{index}", "monster_id": monster_id,
        "_monster_name": "Xu Wu", "started_at": start,
        "ended_at": start + timedelta(seconds=110),
        "quest_time_seconds": 110.0, "cart_count": 0, "cleared": True,
        "hunterpie_version": "t", "game_version": "g", "source": "hunterpie",
        "players": [
            {"display_name": name, "weapon_id": 6, "total_damage": dmg,
             "peak_dps": 50.0, "is_supporter": False}
            for name, dmg in damage.items()
        ],
        # Every hunter shots from 10s to 110s: a 100s window for both, so
        # DPS is exactly damage / 100 regardless of the window mode.
        "snapshots": [
            {"display_name": name, "ts_offset_seconds": t,
             "cumulative_damage": dmg * (t - 10) / 100, "instant_dps": 10.0}
            for name, dmg in damage.items() for t in (10.0, 60.0, 110.0)
        ],
        "abnormalities": [], "hp_steps": [], "events": [], "player_health": [],
    }


def _isi_id(session):
    return session.query(Player).filter(Player.display_name == "Isi").one().id


def test_share_and_monster_relative_index():
    s = _session()
    for i, (isi, pal) in enumerate([(1000.0, 1000.0), (2000.0, 1000.0),
                                    (1000.0, 3000.0)]):
        upsert_hunt(s, _payload(i, {"Isi": isi, "Pal": pal}))

    data = progress(s, player_id=_isi_id(s), window=2)
    pts = data["points"]
    assert [p["dps"] for p in pts] == pytest.approx([10.0, 20.0, 10.0])
    # Share is measured against the whole party, even though the hunter
    # filter keeps only Isi's rows in `points`.
    assert [p["share"] for p in pts] == pytest.approx([0.5, 2 / 3, 0.25])
    # 100% = Isi's median DPS on Xu Wu (10): 1000 dmg, 2000, 1000.
    assert [p["index"] for p in pts] == pytest.approx([1.0, 2.0, 1.0])

    rolling = data["rolling"]
    assert rolling[1]["avg_index"] == pytest.approx(1.5)
    assert rolling[2]["avg_index"] == pytest.approx(1.5)
    assert rolling[1]["avg_share"] == pytest.approx((0.5 + 2 / 3) / 2)
    assert rolling[2]["avg_share"] == pytest.approx((2 / 3 + 0.25) / 2)
    assert [r["avg_clear"] for r in rolling] == pytest.approx([110.0] * 3)


def test_switching_monsters_is_not_progress():
    """A harder monster with more damage still reads as 100% of your usual."""
    s = _session()
    upsert_hunt(s, _payload(0, {"Isi": 1000.0, "Pal": 1000.0}, monster_id=31))
    upsert_hunt(s, _payload(1, {"Isi": 3000.0, "Pal": 3000.0}, monster_id=32))

    data = progress(s, player_id=_isi_id(s), window=5)
    assert [p["dps"] for p in data["points"]] == pytest.approx([10.0, 30.0])
    assert [p["index"] for p in data["points"]] == pytest.approx([1.0, 1.0])
    assert [p["share"] for p in data["points"]] == pytest.approx([0.5, 0.5])
