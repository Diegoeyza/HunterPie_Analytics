"""Player HP (Survival tab): import, curve/survival math, refresh/enrich,
split-quest scoping, validation, and the v8 migration backfill."""
import os
import tempfile
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app import api
from app.db import dispose_engine, init_db, make_session


def make_client(seed=None):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
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
    return TestClient(api.app), session, path


HP = [(0.0, 1.0), (5.0, 0.8), (10.0, 0.4), (15.0, 0.2), (20.0, 0.9)]


def health_payload(start, source="reframework", with_health=True,
                   external="hp-1"):
    players = [{"display_name": "Isi", "weapon_id": 6,
                "total_damage": 1000.0, "peak_dps": 50.0,
                "is_supporter": False}]
    snaps = [{"display_name": "Isi", "ts_offset_seconds": 10.0 * k,
              "cumulative_damage": 100.0 * k, "instant_dps": 10.0}
             for k in range(1, 6)]
    health = [{"display_name": "Isi", "ts_offset_seconds": t,
               "hp_fraction": f, "red_fraction": 0.0, "max_hp": 150.0}
              for t, f in HP] if with_health else []
    return {
        "quest_id_external": external, "monster_id": 31,
        "_monster_name": "Xu Wu",
        "started_at": start, "ended_at": start + timedelta(seconds=60),
        "quest_time_seconds": 60.0, "cart_count": 0, "cleared": True,
        "hunterpie_version": "t", "game_version": "g", "source": source,
        "players": players, "snapshots": snaps, "player_health": health,
    }


def test_curve_returns_player_hp_and_survival():
    from app.ingest import upsert_hunt

    def seed(s):
        from app.models import Monster, Weapon
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        upsert_hunt(s, health_payload(datetime(2026, 9, 6, 3, 0)))

    client, s, path = make_client(seed)
    try:
        hunt_id = client.get("/api/hunts").json()["hunts"][0]["id"]
        curve = client.get(f"/api/hunts/{hunt_id}/curve").json()
        assert len(curve["player_hp"]) == 1
        pts = curve["player_hp"][0]
        assert pts["player"] == "Isi"
        assert [p["hp"] for p in pts["points"]] == [1.0, 0.8, 0.4, 0.2, 0.9]
        # Normal 5 s heartbeat gaps all count: 4 segments x 5 s = 20 s.
        (row,) = curve["survival"]
        assert row["player"] == "Isi"
        assert row["min_hp"] == 0.2
        assert row["avg_hp"] == 0.6  # (1+.8+.4+.2)*5/20
        assert row["time_below_50"] == 10.0
        assert row["time_below_25"] == 5.0
        assert row["time_full"] == 5.0
        assert row["samples"] == 5
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_survival_stats_skip_loading_gaps():
    """Only gaps within the 5 s heartbeat count; a long loading/alt-tab hole
    must not add time at the last known HP."""
    from app.queries import _survival_stats

    row = _survival_stats([(0.0, 1.0), (5.0, 0.9), (35.0, 0.5)])
    assert row["samples"] == 3
    assert row["avg_hp"] == 1.0       # only the first 5 s counts
    assert row["time_full"] == 5.0
    assert row["time_below_50"] == 0.0
    assert row["min_hp"] == 0.5


def test_hunts_flag_health():
    from app.ingest import upsert_hunt

    def seed(s):
        from app.models import Monster, Weapon
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        upsert_hunt(s, health_payload(datetime(2026, 9, 6, 3, 0),
                                      external="hp-a"))
        upsert_hunt(s, health_payload(datetime(2026, 9, 7, 3, 0),
                                      with_health=False, external="hp-b"))

    client, s, path = make_client(seed)
    try:
        hunts = client.get("/api/hunts").json()["hunts"]
        assert [h["has_health"] for h in hunts] == [False, True]
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_hunterpie_refresh_preserves_player_health():
    from sqlalchemy import func, select

    from app.ingest import upsert_hunt
    from app.models import Monster, PlayerHealthStep, Weapon

    def seed(s):
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        upsert_hunt(s, health_payload(datetime(2026, 9, 6, 3, 0)))

    _, s, path = make_client(seed)
    try:
        hp = health_payload(datetime(2026, 9, 6, 3, 0), source="hunterpie")
        hp.pop("player_health", None)
        upsert_hunt(s, hp)
        n = s.execute(select(func.count(PlayerHealthStep.id))).scalar_one()
        assert n == 5
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_reframework_enrich_attaches_player_health():
    from sqlalchemy import func, select

    from app.ingest import upsert_hunt
    from app.models import Monster, PlayerHealthStep, Weapon

    def seed(s):
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        upsert_hunt(s, health_payload(datetime(2026, 9, 6, 3, 0),
                                      source="hunterpie",
                                      with_health=False))

    _, s, path = make_client(seed)
    try:
        upsert_hunt(s, health_payload(datetime(2026, 9, 6, 3, 0)))
        n = s.execute(select(func.count(PlayerHealthStep.id))).scalar_one()
        assert n == 5
        # Repeated enriches must not duplicate rows.
        upsert_hunt(s, health_payload(datetime(2026, 9, 6, 3, 0)))
        n = s.execute(select(func.count(PlayerHealthStep.id))).scalar_one()
        assert n == 5
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_player_health_validation():
    import pytest

    from app.ingest import upsert_hunt
    from app.models import Monster, Weapon

    _, s, path = make_client()
    try:
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        bad = health_payload(datetime(2026, 9, 6, 3, 0))
        bad["player_health"][0]["hp_fraction"] = 1.5
        with pytest.raises(ValueError):
            upsert_hunt(s, bad)
        bad = health_payload(datetime(2026, 9, 6, 3, 0), external="hp-x2")
        bad["player_health"][0]["red_fraction"] = -0.1
        with pytest.raises(ValueError):
            upsert_hunt(s, bad)
        bad = health_payload(datetime(2026, 9, 6, 3, 0), external="hp-x3")
        bad["player_health"][0]["hp_fraction"] = None
        with pytest.raises(ValueError):
            upsert_hunt(s, bad)
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_split_quest_health_primary_only():
    from app.import_hunt import poogie_to_payloads

    def monster(mid):
        return {"id": mid, "variant": 0, "max_health": 15000.0,
                "crown": 0, "enrage": {"activations": []},
                "hunt_started_at": "2026-09-06T03:33:30Z",
                "hunt_finished_at": "2026-09-06T03:36:00Z",
                "hunt_type": 1,
                "health_steps": [
                    {"percentage": 1.0, "time": "2026-09-06T03:33:30Z"},
                    {"percentage": 0.3, "time": "2026-09-06T03:36:00Z"},
                ]}

    doc = {
        "game_type": 2, "source": "reframework",
        "started_at": "2026-09-06T03:33:06Z",
        "finished_at": "2026-09-06T03:36:02Z",
        "quest": {"id": 543, "type": 0, "deaths": 0, "max_deaths": 3,
                  "level": 1, "stars": 6},
        "players": [{
            "name": "Isi", "weapon": 5,
            "damages": [{"damage": 100.0,
                         "dealt_at": "2026-09-06T03:34:00Z"}],
            "health_steps": [
                {"percentage": 0.9, "red_percentage": 0.1,
                 "max_hp": 150.0, "time": "2026-09-06T03:34:00Z"},
                {"percentage": 0.5, "red_percentage": 0.0,
                 "max_hp": 150.0, "time": "2026-09-06T03:35:00Z"},
            ],
        }],
        "monsters": [monster(31), monster(1)],
        "hash": "split-hp",
    }
    payloads = poogie_to_payloads(doc, {31: "Xu Wu", 1: "Blangonga"},
                                  "hv", "gv")
    assert len(payloads) == 2
    assert len(payloads[0][0]["player_health"]) == 2
    assert payloads[0][0]["player_health"][0]["hp_fraction"] == 0.9
    assert payloads[0][0]["player_health"][0]["red_fraction"] == 0.1
    # Quest-wide HP stays on every sibling (Survival reads one hunt at a time).
    assert len(payloads[1][0]["player_health"]) == 2


def test_migrate_v8_backfills_table():
    from sqlalchemy import text

    import app.db as dbmod

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        dbmod.init_db(path)
        eng = dbmod.get_engine(path)
        with eng.begin() as conn:
            conn.execute(text("DROP TABLE player_health_steps"))
            conn.execute(text("PRAGMA user_version=7"))
        assert dbmod.migrate(db_path=path) == dbmod.LATEST_VERSION
        with eng.connect() as conn:
            tables = {r[0] for r in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"))}
            assert "player_health_steps" in tables
            # v9: mod version column for the reinstall notice.
            cols = {r[1] for r in conn.execute(text(
                "PRAGMA table_info(hunts)"))}
            assert "mod_version" in cols
        # Idempotent rerun.
        assert dbmod.migrate(db_path=path) == dbmod.LATEST_VERSION
    finally:
        dbmod.dispose_engine(path)
        os.unlink(path)


def _abn_payload(start, source, abn, external="abn-1"):
    p = health_payload(start, source=source, with_health=False,
                       external=external)
    p["abnormalities"] = abn
    return p


def _abn(ab_id="Songs_Songs.12", category="Songs"):
    return {"display_name": "Isi", "abnormality_id": ab_id,
            "category": category, "started_at_offset": 5.0,
            "finished_at_offset": 20.0}


def test_ingest_drops_buildup_meters_keeps_timed_debuffs():
    """Buildup gauges are not timed windows: the import keeps only the
    displayable companion row from the same payload."""
    from sqlalchemy import select

    from app.ingest import upsert_hunt
    from app.models import Monster, PlayerAbnormality, Weapon

    def seed(s):
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        upsert_hunt(s, _abn_payload(
            datetime(2026, 9, 6, 3, 0), "hunterpie",
            [_abn("Debuffs_Debuffs.0.BuildUp", "Debuffs"),
             _abn("Debuffs_Debuffs.0", "Debuffs")]))

    _, s, path = make_client(seed)
    try:
        rows = s.execute(select(PlayerAbnormality)).scalars().all()
        assert [r.abnormality_id for r in rows] == ["Debuffs_Debuffs.0"]
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_has_buffs_ignores_buildup_only_hunt():
    """Legacy buildup rows may already be in a DB; `/hunts` must not flag
    them, and the abnormalities endpoint must not display them."""
    from sqlalchemy import select

    from app.ingest import upsert_hunt
    from app.models import (Hunt, Monster, Player, PlayerAbnormality, Weapon)

    def seed(s):
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        upsert_hunt(s, health_payload(datetime(2026, 9, 6, 3, 0),
                                      source="hunterpie"))

    client, s, path = make_client(seed)
    try:
        hunt_id = s.execute(select(Hunt.id)).scalar_one()
        player_id = s.execute(select(Player.id).where(
            Player.display_name == "Isi")).scalar_one()
        s.add(PlayerAbnormality(
            hunt_id=hunt_id, player_id=player_id,
            abnormality_id="Debuffs_Debuffs.0.BuildUp", category="Debuffs",
            started_at_offset=5.0, finished_at_offset=20.0))
        s.commit()
        hunts = client.get("/api/hunts").json()["hunts"]
        assert [h["has_buffs"] for h in hunts] == [False]
        detail = client.get(f"/api/hunts/{hunt_id}/abnormalities").json()
        assert detail["players"] == []
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_mod_buffs_are_never_stored():
    """A REFramework payload's abnormalities are dropped at ingest itself, not
    merely overwritten by a later companion refresh."""
    from sqlalchemy import select

    from app.ingest import upsert_hunt
    from app.models import Monster, PlayerAbnormality, Weapon

    def seed(s):
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()

    _, s, path = make_client(seed)
    try:
        upsert_hunt(s, _abn_payload(datetime(2026, 9, 6, 3, 0),
                                    "reframework", [_abn()]))
        assert s.execute(select(PlayerAbnormality)).scalars().all() == []

        upsert_hunt(s, health_payload(datetime(2026, 9, 6, 3, 0),
                                      source="hunterpie"))
        assert s.execute(select(PlayerAbnormality)).scalars().all() == []
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_mod_only_hunt_does_not_serve_legacy_buff_rows():
    """Legacy rows can survive on a mod-only hunt; reads must still hide them,
    because buffs are companion-only."""
    from sqlalchemy import select

    from app.ingest import upsert_hunt
    from app.models import (Hunt, Monster, Player, PlayerAbnormality, Weapon)

    def seed(s):
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        upsert_hunt(s, health_payload(datetime(2026, 9, 6, 3, 0),
                                      source="reframework"))

    client, s, path = make_client(seed)
    try:
        # Bypass ingest: this is an old row the companion-only gate never saw.
        hunt_id = s.execute(select(Hunt.id)).scalar_one()
        player_id = s.execute(select(Player.id).where(
            Player.display_name == "Isi")).scalar_one()
        s.add(PlayerAbnormality(
            hunt_id=hunt_id, player_id=player_id,
            abnormality_id="Songs_Songs.12", category="Songs",
            started_at_offset=5.0, finished_at_offset=20.0))
        s.commit()

        hunts = client.get("/api/hunts").json()["hunts"]
        detail = client.get(f"/api/hunts/{hunt_id}/abnormalities").json()
        assert [h["has_buffs"] for h in hunts] == [False]
        assert detail["players"] == []
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_companion_buffs_are_stored():
    """The companion is the only buff source, so its rows are stored."""
    from sqlalchemy import select

    from app.ingest import upsert_hunt
    from app.models import Monster, PlayerAbnormality, Weapon

    def seed(s):
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        upsert_hunt(s, _abn_payload(datetime(2026, 9, 6, 3, 0),
                                    "reframework", [_abn()]))

    _, s, path = make_client(seed)
    try:
        upsert_hunt(s, _abn_payload(
            datetime(2026, 9, 6, 3, 0), "hunterpie",
            [_abn("Consumables_Consumables.88", "Consumables")]))
        rows = s.execute(select(PlayerAbnormality)).scalars().all()
        assert [r.abnormality_id for r in rows] == [
            "Consumables_Consumables.88"]
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_enrich_never_attaches_mod_buffs():
    """Enriching a companion hunt with a REFramework payload must attach no
    abnormalities, and repeating the enrich stays empty."""
    from sqlalchemy import select

    from app.ingest import upsert_hunt
    from app.models import Monster, PlayerAbnormality, Weapon

    def seed(s):
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        upsert_hunt(s, health_payload(datetime(2026, 9, 6, 3, 0),
                                      source="hunterpie"))

    _, s, path = make_client(seed)
    try:
        upsert_hunt(s, _abn_payload(datetime(2026, 9, 6, 3, 0),
                                    "reframework", [_abn()]))
        rows = s.execute(select(PlayerAbnormality)).scalars().all()
        assert rows == []
        # Idempotent: a second enrich still writes nothing.
        upsert_hunt(s, _abn_payload(datetime(2026, 9, 6, 3, 0),
                                    "reframework", [_abn()]))
        rows = s.execute(select(PlayerAbnormality)).scalars().all()
        assert rows == []
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_late_companion_start_merges_into_mod_hunt():
    """Companion launched 78 s into a hunt: damage totals agree, so the two
    dumps must unify (DPS + the mod's HP on one hunt), not duplicate."""
    from sqlalchemy import select

    from app.ingest import upsert_hunt
    from app.models import DpsSnapshot, Hunt, Monster, PlayerHealthStep, Weapon

    start = datetime(2026, 9, 6, 3, 0)

    def seed(s):
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        mod = health_payload(start)  # reframework, 1000 damage, HP samples
        upsert_hunt(s, mod)

    _, s, path = make_client(seed)
    try:
        late = health_payload(start + timedelta(seconds=78),
                              source="hunterpie", with_health=False,
                              external="late-companion")
        late["players"][0]["total_damage"] = 1000.0  # same quest, same total
        # Importer offsets are relative to the dump's own started_at (attach
        # time), so the late companion starts at 0, not 78.
        late["snapshots"] = [
            {"display_name": "Isi", "ts_offset_seconds": 5.0 * k,
             "cumulative_damage": 100.0 * (k + 1), "instant_dps": 20.0}
            for k in range(5)
        ]
        upsert_hunt(s, late)
        hunts = s.execute(select(Hunt)).scalars().all()
        assert len(hunts) == 1
        assert hunts[0].source == "hunterpie"
        snaps = s.execute(select(DpsSnapshot)).scalars().all()
        assert len(snaps) == 5
        # Companion offsets are rebased onto the mod's earlier (true) start:
        # 78 s late + 5/10/15/20/25 s after attach.
        assert [round(x.ts_offset_seconds) for x in snaps] == [78, 83, 88, 93, 98]
        # The mod's HP survived the refresh, unshifted (already true-relative).
        hp = s.execute(select(PlayerHealthStep)).scalars().all()
        assert len(hp) == 5
        assert [x.ts_offset_seconds for x in hp] == [0.0, 5.0, 10.0, 15.0, 20.0]
        # True quest start, not the attach time.
        assert hunts[0].started_at == start
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_early_companion_then_mod_enriches_aligns_hp():
    """Companion attached before the mod: the mod's HP offsets are relative
    to its later start, so they must move forward onto the companion timeline
    (otherwise the HP curve sits ~14 s before the DPS curve)."""
    from sqlalchemy import select

    from app.ingest import upsert_hunt
    from app.models import Hunt, Monster, PlayerHealthStep, Weapon

    start = datetime(2026, 9, 6, 3, 0)

    def seed(s):
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        upsert_hunt(s, health_payload(start, source="hunterpie",
                                      with_health=False, external="pie-early"))

    _, s, path = make_client(seed)
    try:
        upsert_hunt(s, health_payload(start + timedelta(seconds=14),
                                      external="rf-late"))
        hunt = s.execute(select(Hunt)).scalar_one()
        assert hunt.source == "hunterpie"
        assert hunt.started_at == start
        hp = s.execute(
            select(PlayerHealthStep).order_by(PlayerHealthStep.ts_offset_seconds)
        ).scalars().all()
        assert [round(x.ts_offset_seconds) for x in hp] == [14, 19, 24, 29, 34]
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_early_companion_refresh_shifts_mod_hp():
    """Reverse order: a mod-created hunt is refreshed by a companion whose
    clock started 14 s earlier; the preserved HP samples must shift with the
    new (earlier) origin."""
    from sqlalchemy import select

    from app.ingest import upsert_hunt
    from app.models import Hunt, Monster, PlayerHealthStep, Weapon

    start = datetime(2026, 9, 6, 3, 0)

    def seed(s):
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        upsert_hunt(s, health_payload(start, external="rf-early"))

    _, s, path = make_client(seed)
    try:
        upsert_hunt(s, health_payload(start - timedelta(seconds=14),
                                      source="hunterpie", with_health=False,
                                      external="pie-early"))
        hunt = s.execute(select(Hunt)).scalar_one()
        assert hunt.source == "hunterpie"
        assert hunt.started_at == start - timedelta(seconds=14)
        hp = s.execute(
            select(PlayerHealthStep).order_by(PlayerHealthStep.ts_offset_seconds)
        ).scalars().all()
        assert [round(x.ts_offset_seconds) for x in hp] == [14, 19, 24, 29, 34]
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_sibling_hunt_borrows_quest_player_hp():
    """A monster the mod skipped keeps Survival data via its quest sibling."""
    from app.ingest import upsert_hunt
    from app.models import Monster, Weapon

    start = datetime(2026, 9, 6, 3, 0)

    def seed(s):
        s.add_all([Monster(id=31, name="Xu Wu"), Monster(id=1, name="Arkveld"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        a = health_payload(start, external="sib-a")
        upsert_hunt(s, a)
        b = health_payload(start, external="sib-b")
        b["monster_id"] = 1
        b["_monster_name"] = "Arkveld"
        b["player_health"] = []
        upsert_hunt(s, b)

    client, s, path = make_client(seed)
    try:
        hunts = client.get("/api/hunts").json()["hunts"]
        other = next(h for h in hunts if h["monster"] == "Arkveld")
        assert other["has_health"] is False  # nothing stored on that row
        curve = client.get(f"/api/hunts/{other['id']}/curve").json()
        assert curve["player_hp"], "sibling should borrow the quest's HP"
        assert curve["survival"][0]["samples"] == 5
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_dps_curve_starts_at_quest_origin():
    """First-hit damage curves are anchored at t=0 so they share the HP axis."""
    from app.queries import _anchor_dps_origin
    pts = [{"t": 40.0, "dmg": 500.0, "dps": 10.0},
           {"t": 90.0, "dmg": 5000.0, "dps": 90.0}]
    _anchor_dps_origin(pts)
    assert pts[0] == {"t": 0.0, "dmg": 0.0, "dps": 0.0}
    assert pts[1]["t"] == 40.0


def test_late_attach_dps_is_not_anchored():
    """A bulk first sample means the companion attached mid-hunt: no fake 0s."""
    from app.queries import _anchor_dps_origin
    pts = [{"t": 78.9, "dmg": 10870.0, "dps": 137.0},
           {"t": 167.0, "dmg": 18186.0, "dps": 80.0}]
    _anchor_dps_origin(pts)
    assert len(pts) == 2 and pts[0]["t"] == 78.9


def test_purge_mod_abnormalities_removes_only_mod_only_hunts():
    """Legacy cleanup: stale buffs on mod-only hunts go, companion hunts stay."""
    from sqlalchemy import select

    from app.db import purge_mod_abnormalities
    from app.ingest import upsert_hunt
    from app.models import Hunt, Monster, Player, PlayerAbnormality, Weapon

    def seed(s):
        s.add_all([Monster(id=31, name="Xu Wu"),
                   Weapon(id=6, name="HuntingHorn",
                          weapon_type="HuntingHorn")])
        s.flush()
        upsert_hunt(s, health_payload(datetime(2026, 9, 6, 3, 0),
                                      source="hunterpie"))
        upsert_hunt(s, health_payload(datetime(2026, 9, 7, 3, 0),
                                      source="reframework"))

    _, s, path = make_client(seed)
    try:
        # Legacy rows predate the companion-only gate, so insert them directly.
        hunts = {h.source: h.id for h in s.execute(select(Hunt)).scalars()}
        player_id = s.execute(select(Player.id).where(
            Player.display_name == "Isi")).scalar_one()
        for hunt_id in hunts.values():
            s.add(PlayerAbnormality(
                hunt_id=hunt_id, player_id=player_id,
                abnormality_id="Songs_Songs.12", category="Songs",
                started_at_offset=5.0, finished_at_offset=20.0))
        s.commit()

        deleted = purge_mod_abnormalities(s)

        remaining = s.execute(
            select(PlayerAbnormality.hunt_id)).scalars().all()
        assert deleted == 1
        assert remaining == [hunts["hunterpie"]]
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)
