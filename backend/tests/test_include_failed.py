"""Global "include failed hunts" toggle.

Performance stats use cleared hunts unless ``include_failed=1``; clear-rate
metrics always count failures regardless of the toggle.
"""
import os
import tempfile
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import api
from app.db import dispose_engine, init_db, make_session
from app.ingest import upsert_hunt

_TEST_DBS: list[str] = []
_SEED_SESSIONS: list = []


def make_client(seed=None):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    _TEST_DBS.append(path)
    init_db(path)
    session = make_session(path)
    _SEED_SESSIONS.append(session)
    if seed:
        seed(session)

    def _override():
        s = make_session(path)
        try:
            yield s
        finally:
            s.close()

    api.app.dependency_overrides[api.get_db] = _override
    return TestClient(api.app), session


def teardown_function():
    api.app.dependency_overrides.clear()
    while _SEED_SESSIONS:
        _SEED_SESSIONS.pop().close()
    while _TEST_DBS:
        path = _TEST_DBS.pop()
        dispose_engine(path)
        if os.path.exists(path):
            os.remove(path)


def _hunt(s, *, hid: int, cleared: bool, damage: float, start: datetime):
    """One hunt for hunter 'Isi'; engagement window = 100-10 = 90s."""
    upsert_hunt(s, {
        "quest_id_external": f"q{hid}", "dedup_hash": f"h{hid}",
        "monster_id": 27, "_monster_name": "Arkveld",
        "started_at": start, "ended_at": start,
        "quest_time_seconds": 300.0, "cart_count": 0 if cleared else 3,
        "cleared": cleared, "hunterpie_version": "t", "game_version": "g",
        "players": [{"display_name": "Isi", "weapon_id": 6,
                     "total_damage": damage, "peak_dps": damage / 100.0,
                     "is_supporter": False}],
        "snapshots": [{"display_name": "Isi", "ts_offset_seconds": 10.0,
                       "cumulative_damage": damage / 2, "instant_dps": 40.0},
                      {"display_name": "Isi", "ts_offset_seconds": 100.0,
                       "cumulative_damage": damage, "instant_dps": 50.0}],
        "hp_steps": [{"ts_offset_seconds": 10.0, "hp_fraction": 0.9},
                     {"ts_offset_seconds": 100.0, "hp_fraction": 0.1}],
        "events": [],
    })


def seed_mixed(s):
    from app.models import Monster, Weapon
    s.add_all([Monster(id=27, name="Arkveld"),
               Weapon(id=6, name="HuntingHorn", weapon_type="HuntingHorn")])
    s.flush()
    _hunt(s, hid=1, cleared=True, damage=20000.0,
          start=datetime(2026, 10, 1, 10, 0))
    _hunt(s, hid=2, cleared=False, damage=40000.0,
          start=datetime(2026, 10, 2, 10, 0))


def test_leaderboard_excludes_failed_by_default():
    client, _s = make_client(seed_mixed)
    default = client.get("/api/leaderboard").json()["leaders"]
    assert default[0]["hunts"] == 1  # cleared hunt only
    allin = client.get("/api/leaderboard",
                       params={"include_failed": "true"}).json()["leaders"]
    assert allin[0]["hunts"] == 2  # failed hunt now counts


def test_progress_excludes_failed_by_default():
    client, _s = make_client(seed_mixed)
    assert len(client.get("/api/progress").json()["points"]) == 1
    body = client.get("/api/progress", params={"include_failed": "true"}).json()
    assert len(body["points"]) == 2


def test_high_scores_excludes_failed_by_default():
    client, _s = make_client(seed_mixed)
    assert len(client.get("/api/high-scores").json()["scores"]) == 1
    body = client.get("/api/high-scores",
                      params={"include_failed": "true"}).json()
    assert len(body["scores"]) == 2


def test_weapons_avg_dps_pool_but_clear_rate_counts_failures():
    """Avg/peak DPS follow the toggle; clear rate spans every attempt."""
    client, _s = make_client(seed_mixed)
    w = client.get("/api/weapons").json()["weapons"][0]
    assert w["hunts"] == 2
    assert w["clear_rate"] == pytest.approx(0.5)
    assert w["avg_dps"] == pytest.approx(20000.0 / 90.0)  # cleared only
    assert w["peak_dps"] == pytest.approx(200.0)

    w_all = client.get("/api/weapons", params={"include_failed": "true"}).json()
    w_all = w_all["weapons"][0]
    assert w_all["clear_rate"] == pytest.approx(0.5)  # rate unchanged
    assert w_all["avg_dps"] == pytest.approx(60000.0 / 180.0)  # both hunts
    assert w_all["peak_dps"] == pytest.approx(400.0)


def test_synergy_clear_rate_counts_failures():
    client, _s = make_client(seed_mixed)
    default = client.get("/api/synergy").json()["pairings"][0]
    assert default["clear_rate"] == pytest.approx(0.5)
    assert default["hunts"] == 2
