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


def test_sos_join_dps_uses_own_window():
    """Late (SOS) joiner: DPS = own damage / own tracked window, not the
    party-wide first-hit→death window (regression: showed ~2x real DPS)."""
    from app.ingest import upsert_hunt
    from app.models import Monster, Weapon

    client, s = make_client()
    s.add_all([Monster(id=8, name="Lagiacrus"),
               Weapon(id=6, name="HuntingHorn", weapon_type="HuntingHorn"),
               Weapon(id=1, name="GreatSword", weapon_type="GreatSword")])
    s.flush()
    upsert_hunt(s, {
        "quest_id_external": "sos", "dedup_hash": "sos",
        "monster_id": 8, "_monster_name": "Lagiacrus",
        "started_at": datetime(2026, 9, 7, 1, 0),
        "ended_at": datetime(2026, 9, 7, 1, 10),
        "quest_time_seconds": 587.0,
        "cart_count": 0, "cleared": True,
        "hunterpie_version": "t", "game_version": "g",
        "players": [
            {"display_name": "Isi", "weapon_id": 6,
             "total_damage": 23385.0, "peak_dps": 300.0, "is_supporter": False},
            {"display_name": "Host", "weapon_id": 1,
             "total_damage": 12909.0, "peak_dps": 150.0, "is_supporter": False},
        ],
        # Isi joins mid-fight (first snapshot at 33s); host tracked from 7s.
        # HP tracking goes stale early (last step 67s) while damage runs to 152s.
        "snapshots": [
            {"display_name": "Isi", "ts_offset_seconds": 33.0,
             "cumulative_damage": 100.0, "instant_dps": 50.0},
            {"display_name": "Isi", "ts_offset_seconds": 152.0,
             "cumulative_damage": 23385.0, "instant_dps": 190.0},
            {"display_name": "Host", "ts_offset_seconds": 7.0,
             "cumulative_damage": 50.0, "instant_dps": 40.0},
            {"display_name": "Host", "ts_offset_seconds": 152.0,
             "cumulative_damage": 12909.0, "instant_dps": 85.0},
        ],
        "hp_steps": [{"ts_offset_seconds": 7.0, "hp_fraction": 1.0},
                     {"ts_offset_seconds": 67.0, "hp_fraction": 0.25}],
        "events": [],
    })
    scores = client.get("/api/high-scores").json()["scores"]
    assert len(scores) == 1
    # Isi 23385 / (152 - 33) = 196.5 — old code gave 23385 / (67 - 7) = 389.8
    assert abs(scores[0]["dps"] - 196.5) < 0.1
    assert scores[0]["player"] == "Isi"


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
    assert set(curve["players"][0]["points"][0]) == {"t", "dmg", "dps"}
    assert client.get("/api/hunts/9999/curve").status_code == 404


def test_curve_quest_hp_returns_all_quest_monsters():
    """Multi-monster quest: quest_hp=1 returns every sibling hunt's HP
    steps so the curve view can draw all monsters' HP at once."""
    from app.ingest import upsert_hunt
    from app.models import Monster, Weapon

    client, s = make_client()
    s.add_all([Monster(id=8, name="Lagiacrus"),
               Monster(id=1, name="Rathalos"),
               Weapon(id=6, name="HuntingHorn", weapon_type="HuntingHorn")])
    s.flush()
    start = datetime(2026, 9, 7, 2, 0)
    for hid, mid, mname in ((1, 8, "Lagiacrus"), (2, 1, "Rathalos")):
        upsert_hunt(s, {
            "quest_id_external": f"q{hid}", "dedup_hash": f"qh{hid}",
            "monster_id": mid, "_monster_name": mname,
            "started_at": start, "ended_at": datetime(2026, 9, 7, 2, 5),
            "quest_time_seconds": 300.0, "cart_count": 0, "cleared": True,
            "hunterpie_version": "t", "game_version": "g",
            "players": [{"display_name": "Isi", "weapon_id": 6,
                         "total_damage": 9000.0, "peak_dps": 60.0,
                         "is_supporter": False}],
            "snapshots": [{"display_name": "Isi", "ts_offset_seconds": 10.0,
                           "cumulative_damage": 4500.0, "instant_dps": 40.0}],
            "hp_steps": [{"ts_offset_seconds": 10.0, "hp_fraction": 0.9},
                         {"ts_offset_seconds": 20.0, "hp_fraction": 0.8}],
            "events": [],
        })
    hunt_id = client.get("/api/hunts").json()["hunts"][0]["id"]
    plain = client.get(f"/api/hunts/{hunt_id}/curve").json()
    assert "quest_hp" not in plain
    quest = client.get(f"/api/hunts/{hunt_id}/curve", params={"quest_hp": 1}).json()
    assert {q["monster"] for q in quest["quest_hp"]} == {"Lagiacrus", "Rathalos"}
    assert all(len(q["points"]) == 2 for q in quest["quest_hp"])


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


def test_multi_monster_quest_reads_as_one_quest():
    """Same quest_id, two monsters: /quests shows one row with combined
    names and /filter-options one option (no duplicate values)."""
    from app.ingest import upsert_hunt
    from app.models import Monster, Weapon

    def seed(s):
        s.add_all([Monster(id=31, name="Xu Wu"), Monster(id=27, name="Arkveld"),
                   Weapon(id=6, name="HuntingHorn", weapon_type="HuntingHorn")])
        s.flush()
        base = {
            "hunterpie_version": "t", "game_version": "g",
            "cart_count": 0, "cleared": True, "quest_time_seconds": 180.0,
            "players": [{"display_name": "Isi", "weapon_id": 6,
                         "total_damage": 9000.0, "peak_dps": 60.0,
                         "is_supporter": False}],
            "snapshots": [], "events": [],
        }
        upsert_hunt(s, {**base, "dedup_hash": "m1", "monster_id": 31,
                         "started_at": datetime(2026, 9, 1, 3, 0),
                         "quest_id": 558, "quest_stars": 10,
                         "monster_max_hp": 18450.0})
        upsert_hunt(s, {**base, "dedup_hash": "m2", "monster_id": 27,
                         "started_at": datetime(2026, 9, 1, 3, 0),
                         "quest_id": 558, "quest_stars": 10,
                         "monster_max_hp": 240000.0})

    client, _ = make_client(seed)
    quests = client.get("/api/quests").json()["quests"]
    assert len(quests) == 1
    assert quests[0]["quest_id"] == 558 and quests[0]["hunts"] == 2
    assert quests[0]["monster"] == "Xu Wu + Arkveld"
    opts = client.get("/api/filter-options").json()["quests"]
    assert [o["quest_id"] for o in opts] == [558]
    assert opts[0]["monster"] == "Xu Wu + Arkveld"


def test_high_scores():
    client, _ = make_client(seed_two_hunts)
    # hunt 1 = solo Isi (5.6 dps), hunt 2 = Isi (8.3) + Pal (2.1)
    # one row per hunt, default sort = dps: hunt 2, hunt 1
    scores = client.get("/api/high-scores").json()["scores"]
    assert [s["hunt_id"] for s in scores] == [2, 1]
    assert [s["rank"] for s in scores] == [1, 2]
    top = scores[0]
    assert top["monster"] == "Xu Wu" and top["player"] == "Isi"
    assert top["weapon"] == "HuntingHorn" and top["dps"] > 0
    assert [m["player"] for m in top["party"]] == ["Pal"]
    solo = scores[1]
    assert solo["party"] == []

    # top-N limit
    assert len(client.get("/api/high-scores",
                          params={"limit": 1}).json()["scores"]) == 1

    # sort by fastest clear: hunt 1 (180s) before hunt 2 (240s)
    by_time = client.get("/api/high-scores",
                         params={"sort_by": "time"}).json()["scores"]
    assert [s["hunt_id"] for s in by_time] == [1, 2]

    assert client.get("/api/high-scores",
                      params={"monster_id": 999}).json()["scores"] == []

    # global hunter scope: hunts including Pal, featured = Pal's own DPS
    pal_id = next(p["id"] for p in
                  client.get("/api/filter-options").json()["players"]
                  if p["name"] == "Pal")
    scoped = client.get("/api/high-scores",
                        params={"player_ids": str(pal_id)}).json()["scores"]
    assert len(scoped) == 1 and scoped[0]["player"] == "Pal"
    assert [m["player"] for m in scoped[0]["party"]] == ["Isi"]

    # weapon filter narrows the pool to weapon users, then features the best
    # of them: GreatSword (id 1) is Pal's — hunt 2 lists Pal even unscoped
    unscoped_gs = client.get("/api/high-scores",
                             params={"weapon_id": 1}).json()["scores"]
    assert len(unscoped_gs) == 1 and unscoped_gs[0]["player"] == "Pal"
    scoped_gs = client.get("/api/high-scores",
                           params={"weapon_id": 1,
                                   "player_ids": str(pal_id)}).json()["scores"]
    assert len(scoped_gs) == 1 and scoped_gs[0]["player"] == "Pal"


def test_leaderboard():
    """Per-hunter ranking over cleared hunts: filters, min_hunts gate,
    scope narrows to scoped hunters only."""
    from app.ingest import upsert_hunt

    client, s = make_client(seed_two_hunts)
    # Uncleared hunt for a third hunter: must not appear (cleared-only).
    # (Monster 31 + HuntingHorn already seeded by seed_two_hunts.)
    upsert_hunt(s, {
        "quest_id_external": "q9", "dedup_hash": "h9",
        "monster_id": 31, "_monster_name": "Xu Wu",
        "started_at": datetime(2026, 9, 8, 3, 0),
        "ended_at": datetime(2026, 9, 8, 3, 3),
        "quest_time_seconds": 180.0, "cart_count": 3, "cleared": False,
        "hunterpie_version": "t", "game_version": "g",
        "players": [{"display_name": "Quitter", "weapon_id": 6,
                     "total_damage": 50000.0, "peak_dps": 500.0,
                     "is_supporter": False}],
        "snapshots": [{"display_name": "Quitter", "ts_offset_seconds": 10.0,
                       "cumulative_damage": 25000.0, "instant_dps": 400.0}],
        "events": [],
    })

    leaders = client.get("/api/leaderboard").json()["leaders"]
    assert {r["player"] for r in leaders} == {"Isi", "Pal"}
    isi = next(r for r in leaders if r["player"] == "Isi")
    assert isi["hunts"] == 2 and isi["avg_dps"] > 0
    assert isi["best_dps"] >= isi["avg_dps"]
    # default sort: avg DPS desc
    assert [r["player"] for r in leaders] == sorted(
        [r["player"] for r in leaders],
        key=lambda n: -next(r["avg_dps"] for r in leaders if r["player"] == n))

    # min_hunts gate drops one-off Pal
    gated = client.get("/api/leaderboard", params={"min_hunts": 2}).json()["leaders"]
    assert [r["player"] for r in gated] == ["Isi"]

    # filters narrow the pool
    assert len(client.get("/api/leaderboard",
                          params={"monster_id": 31}).json()["leaders"]) == 2
    assert client.get("/api/leaderboard",
                      params={"monster_id": 999}).json()["leaders"] == []
    assert {r["player"] for r in client.get(
        "/api/leaderboard", params={"weapon_id": 1}).json()["leaders"]} == {"Pal"}

    # scope ranks only scoped hunters
    pal_id = next(p["id"] for p in
                  client.get("/api/filter-options").json()["players"]
                  if p["name"] == "Pal")
    scoped = client.get("/api/leaderboard",
                        params={"player_ids": str(pal_id)}).json()["leaders"]
    assert [r["player"] for r in scoped] == ["Pal"]


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
    con.execute("CREATE TABLE hunt_players (hunt_id INTEGER, player_id INTEGER)")
    con.commit()
    con.close()
    from app.db import init_db
    init_db(path)
    con = sqlite3.connect(path)
    cols = {r[1] for r in con.execute("PRAGMA table_info(hunts)")}
    hp_cols = {r[1] for r in con.execute("PRAGMA table_info(hunt_players)")}
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert {"quest_id", "quest_stars", "monster_max_hp", "monster_crown"} <= cols
    assert {"gear_raw", "gear_element", "gear_affinity"} <= hp_cols
    assert "weapon_identities" in tables


def _seed_gear_hunts(s):
    """Two hunts: one with a gear fingerprint (auto-creates identity),
    one without (Unknown). Returns (isi_id, identity_id)."""
    from app.ingest import upsert_hunt
    from app.models import Monster, Weapon

    s.add_all([Monster(id=8, name="Lagiacrus"),
               Weapon(id=5, name="HuntingHorn", weapon_type="HuntingHorn")])
    s.flush()
    gear = {"raw": 264.0, "element": 560.0, "affinity": 20.0}
    hunt1, _, _ = upsert_hunt(s, {
        "quest_id_external": "g1", "dedup_hash": "gear1",
        "monster_id": 8, "_monster_name": "Lagiacrus",
        "started_at": datetime(2026, 9, 7, 4, 0),
        "ended_at": datetime(2026, 9, 7, 4, 5),
        "quest_time_seconds": 300.0, "cart_count": 0, "cleared": True,
        "hunterpie_version": "t", "game_version": "g",
        "players": [{"display_name": "Isi", "weapon_id": 5, "gear": gear,
                     "total_damage": 9000.0, "peak_dps": 60.0,
                     "is_supporter": False}],
        "snapshots": [{"display_name": "Isi", "ts_offset_seconds": 10.0,
                       "cumulative_damage": 4500.0, "instant_dps": 40.0},
                      {"display_name": "Isi", "ts_offset_seconds": 20.0,
                       "cumulative_damage": 9000.0, "instant_dps": 40.0}],
        "events": [],
    })
    upsert_hunt(s, {
        "quest_id_external": "g2", "dedup_hash": "gear2",
        "monster_id": 8, "_monster_name": "Lagiacrus",
        "started_at": datetime(2026, 9, 7, 5, 0),
        "ended_at": datetime(2026, 9, 7, 5, 5),
        "quest_time_seconds": 300.0, "cart_count": 0, "cleared": True,
        "hunterpie_version": "t", "game_version": "g",
        "players": [{"display_name": "Isi", "weapon_id": 5,
                     "total_damage": 8000.0, "peak_dps": 55.0,
                     "is_supporter": False}],
        "snapshots": [{"display_name": "Isi", "ts_offset_seconds": 10.0,
                       "cumulative_damage": 4000.0, "instant_dps": 40.0},
                      {"display_name": "Isi", "ts_offset_seconds": 20.0,
                       "cumulative_damage": 8000.0, "instant_dps": 40.0}],
        "events": [],
    })
    from app.models import Player, WeaponIdentity
    from sqlalchemy import select
    isi_id = s.execute(select(Player.id)
                       .where(Player.display_name == "Isi")).scalar_one()
    identity = s.execute(select(WeaponIdentity)).scalars().all()
    assert len(identity) == 1
    return isi_id, identity[0].id


def test_gear_import_creates_identity_and_variants():
    client, s = make_client()
    isi_id, identity_id = _seed_gear_hunts(s)
    body = client.get(f"/api/players/{isi_id}/variants").json()
    assert body["unknown_hunts"] == 1
    assert len(body["variants"]) == 1
    v = body["variants"][0]
    assert (v["raw"], v["element"], v["affinity"]) == (264.0, 560.0, 20.0)
    assert v["hunts"] == 1 and v["label"] is None
    # label-once
    renamed = client.patch(f"/api/weapon-identities/{identity_id}",
                           json={"label": "Artian Horn III"}).json()
    assert renamed["label"] == "Artian Horn III"
    assert client.patch("/api/weapon-identities/9999",
                        json={"label": "x"}).status_code == 404
    # label surfaces on high-scores + progress + curve
    scores = client.get("/api/high-scores").json()["scores"]
    assert all(s["variant"] == "Artian Horn III" for s in scores
               if s["hunt_id"] == 1)
    assert all(s["variant"] is None for s in scores if s["hunt_id"] == 2)
    prog = client.get("/api/progress").json()["points"]
    assert {p["variant"] for p in prog} == {"Artian Horn III", None}
    hunt_id = client.get("/api/hunts").json()["hunts"][0]["id"]
    curve = client.get(f"/api/hunts/{hunt_id}/curve").json()
    assert set(curve["players"][0]) >= {"player", "weapon", "variant", "points"}


def test_variant_filter_narrows_scoped_queries():
    client, s = make_client()
    isi_id, identity_id = _seed_gear_hunts(s)
    params = {"player_ids": str(isi_id), "variant_id": identity_id}
    assert {s["hunt_id"] for s in
            client.get("/api/high-scores", params=params).json()["scores"]} == {1}
    assert {p["hunt_id"] for p in
            client.get("/api/progress", params=params).json()["points"]} == {1}
    assert {p["hunt_id"] for p in
            client.get("/api/compare", params=params).json()["points"]} == {1}
    assert client.get("/api/weapons", params=params).json()["weapons"][0]["hunts"] == 1
    assert {p["pairing"] for p in
            client.get("/api/synergy", params=params).json()["pairings"]} == {"Isi"}
    # unknown-variant pseudo id narrows to the gear-less hunt
    unk = dict(params, variant_id=0)
    assert {s["hunt_id"] for s in
            client.get("/api/high-scores", params=unk).json()["scores"]} == {2}
    # bogus identity id narrows to nothing; multi-hunter scope ignores variant
    assert client.get("/api/high-scores",
                      params={"player_ids": str(isi_id),
                              "variant_id": 9999}).json()["scores"] == []
    assert len(client.get(
        "/api/high-scores",
        params={"player_ids": f"{isi_id},999",
                "variant_id": identity_id}).json()["scores"]) == 2


def test_high_scores_weapon_filter_features_weapon_user():
    """Weapon filter narrows the pool to weapon users, scoped or not.

    Regression: unscoped, the filter was checked against the party top-DPS
    player, so hunts where a non-top player used the weapon vanished — while
    scoping to that hunter showed them (adding a filter widened results).
    """
    client, _ = make_client(seed_two_hunts)
    # Hunt 2: Isi (HuntingHorn) tops DPS, Pal (GreatSword) does not.
    # Unscoped GreatSword filter must still list hunt 2, featuring Pal.
    scores = client.get("/api/high-scores", params={"weapon_id": 1}).json()["scores"]
    assert len(scores) == 1
    assert scores[0]["hunt_id"] == 2
    assert scores[0]["player"] == "Pal"
    # HuntingHorn filter lists both hunts, featuring Isi each time.
    scores = client.get("/api/high-scores", params={"weapon_id": 6}).json()["scores"]
    assert {s["hunt_id"] for s in scores} == {1, 2}
    assert {s["player"] for s in scores} == {"Isi"}


def test_progress_improvement():
    client, s = make_client(seed_two_hunts)
    res = client.get("/api/progress/improvement").json()
    assert "top_hunters" in res
    from app.models import Player
    from sqlalchemy import select
    isi_id = s.execute(select(Player.id).where(Player.display_name == "Isi")).scalar_one()
    p_res = client.get(f"/api/progress/improvement?player_id={isi_id}").json()
    assert p_res["player_id"] == isi_id
    assert "groups" in p_res


def test_progress_improvement_weapon_filter():
    """Weapon filter on /progress/improvement narrows results to hunts with that weapon."""
    client, s = make_client(seed_two_hunts)
    # Isi uses HuntingHorn (id=6) in both hunts; Pal uses GreatSword (id=1) in hunt 2.
    # Without filter: top_hunters should include Isi (qualifying groups with >1 instance).
    res_all = client.get("/api/progress/improvement").json()
    assert "top_hunters" in res_all
    assert any(h["player_name"] == "Isi" for h in res_all["top_hunters"])

    # Filter to GreatSword (id=1): only Pal's hunts, but Pal has only 1 instance → no qualifying groups.
    res_gs = client.get("/api/progress/improvement", params={"weapon_id": 1}).json()
    assert "top_hunters" in res_gs
    assert all(h["player_name"] != "Isi" for h in res_gs["top_hunters"])

    # Filter to HuntingHorn (id=6): Isi's 2 hunts on Xu Wu qualify (same monster, >1 instance).
    res_hh = client.get("/api/progress/improvement", params={"weapon_id": 6}).json()
    assert "top_hunters" in res_hh
    isi_hh = [h for h in res_hh["top_hunters"] if h["player_name"] == "Isi"]
    assert len(isi_hh) == 1
    assert isi_hh[0]["qualifying_groups_count"] >= 1

    # Scoped to Isi + weapon filter still returns player data.
    from app.models import Player
    from sqlalchemy import select
    isi_id = s.execute(select(Player.id).where(Player.display_name == "Isi")).scalar_one()
    p_res = client.get(f"/api/progress/improvement?player_id={isi_id}&weapon_id=6").json()
    assert p_res["player_id"] == isi_id
    assert "groups" in p_res


def test_progress_improvement_unknown_player_fallback():
    """Unknown player_id returns a named empty payload, not player_name=''."""
    client, _ = make_client(seed_two_hunts)
    res = client.get("/api/progress/improvement", params={"player_id": 99999}).json()
    assert res["player_id"] == 99999
    assert res["groups"] == []
    assert res["player_name"] == "Player 99999"


def test_progress_improvement_multi_scope_and_filters():
    """player_ids narrows the ranking; monster filter + top_n clamp work."""
    from app.models import Player
    from sqlalchemy import select
    client, s = make_client(seed_two_hunts)
    isi_id = s.execute(select(Player.id).where(Player.display_name == "Isi")).scalar_one()
    pal_id = s.execute(select(Player.id).where(Player.display_name == "Pal")).scalar_one()

    scoped = client.get("/api/progress/improvement",
                        params={"player_ids": f"{isi_id},{pal_id}"}).json()
    assert "top_hunters" in scoped
    assert {h["player_id"] for h in scoped["top_hunters"]} <= {isi_id, pal_id}

    # Monster filter to Xu Wu (31) keeps Isi; bogus monster empties ranking.
    assert any(h["player_name"] == "Isi" for h in client.get(
        "/api/progress/improvement", params={"monster_id": 31}).json()["top_hunters"])
    assert client.get("/api/progress/improvement",
                      params={"monster_id": 9999}).json() == {"top_hunters": []}

    # top_n clamps to >=1 (0 becomes 1) and returns at most that many.
    one = client.get("/api/progress/improvement", params={"top_n": 0}).json()
    assert len(one["top_hunters"]) <= 1

    # Trend stats present on qualifying groups.
    detail = client.get("/api/progress/improvement",
                        params={"player_id": isi_id}).json()
    assert detail["groups"], "Isi should have a qualifying Xu Wu group"
    g = detail["groups"][0]
    for key in ("median_dps", "best_dps", "slope_per_hunt",
                "first_clear_s", "latest_clear_s", "clear_pct_improvement"):
        assert key in g


def _export_doc(hash_: str = "IMPORTOK"):
    """Minimal HuntExports-schema doc (mirrors tests/test_import_hunt)."""
    return {
        "game_type": 2,
        "started_at": "2026-09-06T03:33:06.0749492Z",
        "finished_at": "2026-09-06T03:36:02.3393534Z",
        "uploaded_at": "2026-09-06T03:36:02.3393534Z",
        "quest": {"id": 543, "type": 0, "deaths": 0, "max_deaths": 3,
                  "level": 1, "stars": 6},
        "players": [{
            "name": "Isi", "weapon": 5, "is_hunterpie_user": True,
            "damages": [
                {"damage": 57.0, "dealt_at": "2026-09-06T03:33:30.7341915Z"},
                {"damage": 126.0, "dealt_at": "2026-09-06T03:36:12.4542845Z"},
            ],
            "abnormalities": [],
        }],
        "monsters": [{
            "id": 31, "variant": 5, "max_health": 18450.0, "crown": 0,
            "enrage": {"activations": []},
            "hunt_started_at": "2026-09-06T03:33:30.7334751Z",
            "hunt_finished_at": "2026-09-06T03:36:12.4631848Z",
            "hunt_type": 1, "health_steps": [],
        }],
        "hash": hash_,
    }


def test_import_endpoint(tmp_path, monkeypatch):
    import json
    (tmp_path / "a.json").write_text(json.dumps(_export_doc()))
    (tmp_path / "bad.json").write_text("{not json")
    monkeypatch.setenv("HUNT_EXPORTS", str(tmp_path))
    client, _ = make_client()
    assert client.get("/api/health").json()["hunts"] == 0

    res = client.post("/api/import").json()
    assert res["scanned"] == 2
    assert res["imported"] == 1 and len(res["imported_ids"]) == 1
    assert len(res["errors"]) == 1 and res["errors"][0]["file"] == "bad.json"
    assert client.get("/api/health").json()["hunts"] == 1

    # second call is a dedup no-op
    res2 = client.post("/api/import").json()
    assert res2["imported"] == 0 and res2["duplicates"] == 1

    # missing dir -> 404
    monkeypatch.setenv("HUNT_EXPORTS", str(tmp_path / "nope"))
    assert client.post("/api/import").status_code == 404


def test_ignore_hunt_hides_everywhere_and_restores():
    """PATCH /hunts/{id}/ignore hides the hunt from every stat view;
    include_ignored=1 reveals it with the flag; un-ignoring restores."""
    client, _ = make_client(seed_two_hunts)
    assert client.get("/api/health").json()["hunts"] == 2
    assert client.patch("/api/hunts/9999/ignore",
                        json={"ignored": True}).status_code == 404

    body = client.patch("/api/hunts/2/ignore", json={"ignored": True}).json()
    assert body == {"id": 2, "ignored": True}

    assert client.get("/api/health").json()["hunts"] == 1
    assert [s["hunt_id"] for s in client.get(
        "/api/high-scores").json()["scores"]] == [1]
    assert client.get("/api/progress").json()["points"] == [
        p for p in client.get("/api/progress").json()["points"]
        if p["hunt_id"] == 1]
    assert all(h["id"] == 1 for h in client.get("/api/hunts").json()["hunts"])

    # hidden by default, visible with flag + ignored marker
    assert client.get("/api/hunts").json()["hunts"][0]["ignored"] is False
    shown = client.get("/api/high-scores",
                       params={"include_ignored": 1}).json()["scores"]
    assert {s["hunt_id"] for s in shown} == {1, 2}
    assert [s["ignored"] for s in shown if s["hunt_id"] == 2] == [True]

    # restore
    assert client.patch("/api/hunts/2/ignore",
                        json={"ignored": False}).json()["ignored"] is False
    assert client.get("/api/health").json()["hunts"] == 2
    assert [s["hunt_id"] for s in client.get(
        "/api/high-scores").json()["scores"]] == [2, 1]


