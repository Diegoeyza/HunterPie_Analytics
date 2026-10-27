"""Growth modes: first→last (old behaviour), first-3/last-3 medians, and a
least-squares trend. All damage-based; they differ in how much one lucky or
awful hunt can swing the answer.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db import _on_connect
from app.ingest import upsert_hunt
from app.models import Base, Monster, Player, Weapon
from app.queries import progress_improvement

T0 = datetime(2026, 10, 1, 20, 0, 0)


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    event.listen(engine, "connect", _on_connect)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, future=True)()
    s.add_all([Monster(id=31, name="Xu Wu"),
               Weapon(id=6, name="Hunting Horn", weapon_type="HH")])
    s.commit()
    return s


def _hunt(index: int, isi_damage: float):
    """One hunt where Isi dealt `isi_damage` over a 100s window."""
    start = T0 + timedelta(hours=index)
    return {
        "quest_id_external": f"q{index}", "monster_id": 31,
        "_monster_name": "Xu Wu", "started_at": start,
        "ended_at": start + timedelta(seconds=110),
        "quest_time_seconds": 110.0, "cart_count": 0, "cleared": True,
        "hunterpie_version": "t", "game_version": "g", "source": "hunterpie",
        "players": [{"display_name": "Isi", "weapon_id": 6,
                     "total_damage": isi_damage, "peak_dps": 50.0,
                     "is_supporter": False}],
        "snapshots": [
            {"display_name": "Isi", "ts_offset_seconds": t,
             "cumulative_damage": isi_damage * (t - 10) / 100,
             "instant_dps": 10.0}
            for t in (10.0, 60.0, 110.0)
        ],
        "abnormalities": [], "hp_steps": [], "events": [], "player_health": [],
    }


def _seed(session, dps: list[float]):
    for i, value in enumerate(dps):
        upsert_hunt(session, _hunt(i, value * 100.0))  # 100s window
    return session.query(Player).filter(Player.display_name == "Isi").one().id


def _group(session, pid, mode):
    data = progress_improvement(session, player_id=pid, mode=mode)
    assert data["mode"] == mode
    return data["groups"][0]


def test_modes_measure_the_same_curve_differently():
    s = _session()
    pid = _seed(s, [10.0, 20.0, 30.0, 40.0, 50.0, 60.0])

    first_last = _group(s, pid, "first_last")
    assert first_last["pct_improvement"] == pytest.approx(+500.0)
    assert (first_last["early_dps"], first_last["late_dps"]) == (10.0, 60.0)

    # First 3 median (10,20,30 → 20) vs last 3 (40,50,60 → 50).
    edge = _group(s, pid, "edge_medians")
    assert edge["pct_improvement"] == pytest.approx(+150.0)
    assert (edge["early_dps"], edge["late_dps"]) == (20.0, 50.0)

    # Slope 10/hunt over 5 hunts = +50 DPS on a 35 DPS mean.
    trend = _group(s, pid, "trend")
    assert trend["pct_improvement"] == pytest.approx(+142.9, abs=0.1)
    assert trend["slope_pct_per_hunt"] == pytest.approx(+28.57, abs=0.01)


def test_edge_medians_ignores_a_fluke_first_hunt():
    """One monster-length opener shouldn't turn a rising curve into a crash."""
    s = _session()
    pid = _seed(s, [100.0, 10.0, 20.0, 30.0, 40.0, 50.0])

    assert _group(s, pid, "first_last")["pct_improvement"] == pytest.approx(-50.0)
    # Early median (10,20,30 → 20) vs late (30,40,50 → 40): the fluke is one
    # of three at the start, so growth still reads positive.
    assert _group(s, pid, "edge_medians")["pct_improvement"] == pytest.approx(+100.0)


def test_edge_medians_never_collapses_a_two_hunt_group():
    """Two hunts are the whole group: the edges must not overlap (0%)."""
    s = _session()
    pid = _seed(s, [10.0, 30.0])
    edge = _group(s, pid, "edge_medians")
    assert edge["pct_improvement"] == pytest.approx(+200.0)
    assert (edge["early_dps"], edge["late_dps"]) == (10.0, 30.0)

    # Three hunts: first vs last, the middle one can't join both medians.
    s2 = _session()
    pid2 = _seed(s2, [10.0, 100.0, 30.0])
    edge2 = _group(s2, pid2, "edge_medians")
    assert edge2["pct_improvement"] == pytest.approx(+200.0)


def test_min_instances_and_unknown_mode():
    s = _session()
    pid = _seed(s, [10.0, 20.0, 30.0])

    assert progress_improvement(s, player_id=pid, min_instances=5)["groups"] == []
    # Unknown modes fall back to the old comparison instead of erroring.
    data = progress_improvement(s, player_id=pid, mode="nonsense")
    assert data["mode"] == "first_last"
    assert data["groups"][0]["pct_improvement"] == pytest.approx(+200.0)
