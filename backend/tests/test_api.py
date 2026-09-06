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
    assert {"monsters", "weapons", "players", "quests", "stars"} <= set(opts)
    assert opts["quests"] == [] and opts["stars"] == []


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


def test_quest_star_and_scope_filters():
    from app.ingest import upsert_hunt

    def make_client_with_quests():
        client, s = make_client()
        from datetime import datetime

        from app.models import Monster, Weapon
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn", weapon_type="HuntingHorn")])
        s.flush()
        base = {
            "monster_id": 31, "hunterpie_version": "t", "game_version": "g",
            "cart_count": 0, "cleared": True, "quest_time_seconds": 180.0,
            "players": [{"display_name": "Isi", "weapon_id": 6,
                         "total_damage": 9000.0, "peak_dps": 60.0,
                         "is_supporter": False}],
            "snapshots": [], "events": [],
        }
        upsert_hunt(s, {**base, "dedup_hash": "qa",
                         "started_at": datetime(2026, 9, 1, 3, 0),
                         "quest_id": 543, "quest_stars": 6,
                         "monster_max_hp": 18450.0})
        upsert_hunt(s, {**base, "dedup_hash": "qb",
                         "started_at": datetime(2026, 9, 2, 3, 0),
                         "quest_id": 544, "quest_stars": 5,
                         "monster_max_hp": 15000.0})
        return client, s

    client, s = make_client_with_quests()
    assert len(client.get("/api/progress").json()["points"]) == 2
    assert len(client.get("/api/progress", params={"stars": 6}).json()["points"]) == 1
    assert len(client.get("/api/progress", params={"quest_id": 544}).json()["points"]) == 1
    isi_id = next(p["id"] for p in
                  client.get("/api/filter-options").json()["players"] if p["name"] == "Isi")
    scoped = client.get("/api/progress", params={"player_ids": str(isi_id)}).json()
    assert len(scoped["points"]) == 2
    assert client.get("/api/progress", params={"player_ids": "9999"}).json()["points"] == []

    quests = client.get("/api/quests").json()["quests"]
    assert {q["quest_id"] for q in quests} == {543, 544}
    q543 = next(q for q in quests if q["quest_id"] == 543)
    assert q543["stars"] == 6 and q543["max_hp"] == 18450.0
    assert q543["hunts"] == 1 and q543["best_dps"] == 50.0

    assert len(client.get("/api/records").json()["records"]) == 1
    assert len(client.get("/api/activity").json()["days"]) == 2
    comp = client.get("/api/compare", params={"player_ids": str(isi_id)}).json()
    assert len(comp["points"]) == 2 and comp["scope"] == ["Isi"]
    assert client.get("/api/compare").json()["points"] == []


def test_pins():
    client, _ = make_client(seed_two_hunts)
    assert client.get("/api/players/pins").json() == {"pins": []}
    isi_id = next(p["id"] for p in
                  client.get("/api/filter-options").json()["players"] if p["name"] == "Isi")
    assert client.post(f"/api/players/{isi_id}/pin").json()["pinned"] is True
    pins = client.get("/api/players/pins").json()["pins"]
    assert [p["name"] for p in pins] == ["Isi"]
    assert client.delete(f"/api/players/{isi_id}/pin").json()["pinned"] is False
    assert client.get("/api/players/pins").json() == {"pins": []}
    assert client.post("/api/players/9999/pin").status_code == 404


def test_migration_backfills_old_db():
    import sqlite3

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    _TEST_DBS.append(path)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE hunts (id INTEGER PRIMARY KEY, monster_id INTEGER, "
                "started_at TIMESTAMP)")
    con.commit()
    con.close()
    from app.db import init_db
    init_db(path)
    con = sqlite3.connect(path)
    cols = {r[1] for r in con.execute("PRAGMA table_info(hunts)")}
    con.close()
    assert {"quest_id", "quest_stars", "monster_max_hp", "monster_crown"} <= cols
