"""API tests: one per endpoint, seeded DB + real-hunt shape fixtures."""
import os
import tempfile
from datetime import datetime

from fastapi.testclient import TestClient

from app import api
from app.db import init_db, make_session

_TEST_DBS: list[str] = []


def make_client(seed=None):
    """Temp-file DB: shared across the seed session and per-request sessions
    (in-memory SQLite would give each connection its own empty DB)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    _TEST_DBS.append(path)
    init_db(path)
    session = make_session(path)
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


def seed_two_hunts(s):
    from app.ingest import upsert_hunt
    from app.models import Monster, Weapon

    s.add_all([Monster(id=31, name="Xu Wu"),
               Weapon(id=6, name="HuntingHorn", weapon_type="HuntingHorn"),
               Weapon(id=1, name="GreatSword", weapon_type="GreatSword")])
    s.flush()

    def payload(hid, monster, monster_name, members, start, end):
        # members: [(display_name, weapon_id, total_damage)]
        return {
            "quest_id_external": f"q{hid}", "dedup_hash": f"h{hid}",
            "monster_id": monster, "_monster_name": monster_name,
            "started_at": start, "ended_at": end,
            "quest_time_seconds": (end - start).total_seconds(),
            "cart_count": 0, "cleared": True,
            "hunterpie_version": "t", "game_version": "g",
            "players": [{"display_name": n, "weapon_id": w,
                         "total_damage": dmg, "peak_dps": 50.0,
                         "is_supporter": False} for n, w, dmg in members],
            "snapshots": [{"display_name": n, "ts_offset_seconds": 10.0,
                           "cumulative_damage": dmg / 2, "instant_dps": 40.0}
                          for n, _, dmg in members],
            "events": [],
        }

    upsert_hunt(s, payload(1, 31, "Xu Wu", [("Isi", 6, 1000.0)],
                           datetime(2026, 9, 6, 3, 0), datetime(2026, 9, 6, 3, 3)))
    upsert_hunt(s, payload(2, 31, "Xu Wu", [("Isi", 6, 2000.0), ("Pal", 1, 500.0)],
                           datetime(2026, 9, 7, 3, 0), datetime(2026, 9, 7, 3, 4)))


def teardown_function():
    api.app.dependency_overrides.clear()
    while _TEST_DBS:
        path = _TEST_DBS.pop()
        if os.path.exists(path):
            os.remove(path)


def test_health_empty():
    client, _ = make_client()
    assert client.get("/api/health").json() == {"status": "ok", "hunts": 0}
    opts = client.get("/api/filter-options").json()
    assert set(opts) == {"monsters", "weapons", "players"}


def test_hunts_and_progress():
    client, _ = make_client(seed_two_hunts)
    hunts = client.get("/api/hunts").json()["hunts"]
    assert len(hunts) == 2
    prog = client.get("/api/progress").json()
    assert len(prog["points"]) == 3  # solo Isi + duo Isi/Pal
    assert len(prog["rolling"]) == 3
    assert prog["rolling"][-1]["avg_dps"] > 0
    # filters narrow
    assert len(client.get("/api/progress", params={"monster_id": 31}).json()["points"]) == 3
    assert client.get("/api/progress", params={"monster_id": 999}).json()["points"] == []


def test_weapons_and_synergy():
    client, _ = make_client(seed_two_hunts)
    weapons = client.get("/api/weapons").json()["weapons"]
    names = {w["weapon"] for w in weapons}
    assert "HuntingHorn" in names and "GreatSword" in names
    hh = next(w for w in weapons if w["weapon"] == "HuntingHorn")
    assert hh["hunts"] == 2 and hh["clear_rate"] == 1.0
    pairings = client.get("/api/synergy").json()["pairings"]
    assert {p["pairing"] for p in pairings} == {"Isi", "Isi + Pal"}
    duo = next(p for p in pairings if p["pairing"] == "Isi + Pal")
    assert abs(sum(duo["avg_share"].values()) - 1.0) < 1e-9


def test_curve_and_404():
    client, _ = make_client(seed_two_hunts)
    hunt_id = client.get("/api/hunts").json()["hunts"][0]["id"]
    curve = client.get(f"/api/hunts/{hunt_id}/curve").json()
    assert curve["players"] and curve["players"][0]["points"]
    assert client.get("/api/hunts/9999/curve").status_code == 404
