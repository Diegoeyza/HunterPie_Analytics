"""Hunter highlights (awards): ingest, queries, endpoints."""
import os
import tempfile
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import api
from app.db import dispose_engine, init_db, make_session
from app.models import (
    Award,
    Hunt,
    HuntPlayerAward,
    Monster,
    Weapon,
)

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


def _meta():
    metas = [{"id": i, "name": f"Award {i}", "explain": "x", "unit": 0}
             for i in range(30)]
    metas[4] = {"id": 4, "name": "Established Hunter",
                "explain": "damage dealt", "unit": 0}
    metas[9] = {"id": 9, "name": "Wound Opener",
                "explain": "wounds", "unit": 0}
    return metas


def seed_rich(s):
    s.add_all([Monster(id=27, name="Arkveld"),
               Weapon(id=7, name="HuntingHorn", weapon_type="HuntingHorn")])
    s.flush()
    from app.ingest import upsert_hunt

    def player(name, dmg, awards, wid, wname=None):
        return {"display_name": name, "weapon_id": wid, "weapon_name": wname,
                "total_damage": dmg, "peak_dps": dmg / 10.0,
                "is_supporter": False, "awards": awards}

    payload = {
        "monster_id": 27, "started_at": datetime(2026, 10, 15, 10, 0),
        "ended_at": datetime(2026, 10, 15, 10, 5), "cleared": True,
        "hunterpie_version": "t", "game_version": "g",
        "awards_meta": _meta(),
        "players": [
            player("Isi", 1000.0,
                   [{"id": 4, "count": 1000}, {"id": 9, "count": 3},
                    {"id": 0, "count": 0, "channels": [1, 2, 3, 4]}], 7,
                   wname="Onyx Choros"),
            player("Bob", 500.0, [{"id": 4, "count": 500}], 7),
        ],
        "snapshots": [], "events": [], "hp_steps": [], "abnormalities": [],
    }
    h, _created, _warnings = upsert_hunt(s, payload)
    return h


def teardown_function():
    api.app.dependency_overrides.clear()
    # A seed session still open holds a checked-out connection that
    # dispose() cannot close — release it first, then the pool, then the file.
    while _SEED_SESSIONS:
        _SEED_SESSIONS.pop().close()
    while _TEST_DBS:
        path = _TEST_DBS.pop()
        dispose_engine(path)  # drop pooled connections; Windows can't unlink
        if os.path.exists(path):
            os.remove(path)


def test_awards_persisted():
    _client, s = make_client(seed_rich)
    assert s.execute(select(func.count()).select_from(HuntPlayerAward)
                     ).scalar_one() == 4
    names = set(s.execute(select(Award.name)).scalars().all())
    assert {"Established Hunter", "Wound Opener"} <= names
    # Award 0 (channel array) stores its count as the channel sum.
    ch0 = s.execute(select(HuntPlayerAward.count).where(
        HuntPlayerAward.award_id == 0)).scalar_one()
    assert ch0 == 10.0


def test_hunt_highlights_endpoint():
    client, s = make_client(seed_rich)
    hid = s.execute(select(Hunt.id)).scalar_one()
    body = client.get(f"/api/hunts/{hid}/highlights").json()
    ids = {a["id"]: a["name"] for a in body["awards"]}
    assert ids.get(4) == "Established Hunter"
    shares = {p["player"]: p["damage_share"] for p in body["players"]}
    assert abs(sum(shares.values()) - 1.0) < 1e-9
    isi = next(p for p in body["players"] if p["player"] == "Isi")
    assert {a["id"] for a in isi["awards"]} == {0, 4, 9}


def test_highlights_endpoint():
    client, _s = make_client(seed_rich)
    body = client.get("/api/highlights").json()
    by_name = {a["name"]: a for a in body["awards"]}
    assert by_name["Established Hunter"]["leaders"][0]["player"] == "Isi"
    assert by_name["Wound Opener"]["leaders"][0]["player"] == "Isi"
    assert body["damage_share"][0]["player"] == "Isi"


def test_filter_options_includes_awards():
    client, _s = make_client(seed_rich)
    opts = client.get("/api/filter-options").json()
    assert {a["name"] for a in opts["awards"]} >= {"Established Hunter",
                                                   "Wound Opener"}


def test_player_weapon_names_and_filter():
    client, s = make_client(seed_rich)
    from app.models import Player
    isi = s.execute(select(Player).where(Player.display_name == "Isi")).scalar_one()
    body = client.get(f"/api/players/{isi.id}/weapon-names").json()
    assert body["weapons"] == [{"name": "Onyx Choros", "hunts": 1}]
    assert body["unknown_hunts"] == 0
    # Filtering the hunt list by that weapon name keeps the hunt; another drops it.
    hid = s.execute(select(Hunt.id)).scalar_one()
    hit = client.get("/api/hunts", params={"weapon_name": "Onyx Choros"}).json()
    assert [h["id"] for h in hit["hunts"]] == [hid]
    miss = client.get("/api/hunts", params={"weapon_name": "Nope"}).json()
    assert miss["hunts"] == []


def test_damage_share_uses_full_party_under_scope():
    """A single-hunter scope narrows whose rows are shown, but the damage-share
    denominator stays the full non-supporter party (not just the scoped hunter,
    which would always read 100%)."""
    client, s = make_client(seed_rich)
    from app.models import Player
    isi = s.execute(select(Player).where(Player.display_name == "Isi")).scalar_one()
    body = client.get("/api/highlights",
                      params={"player_ids": str(isi.id)}).json()
    shares = {row["player"]: row["avg_share"] for row in body["damage_share"]}
    assert set(shares) == {"Isi"}  # only the scoped hunter is listed
    assert abs(shares["Isi"] - (1000.0 / 1500.0)) < 1e-9
