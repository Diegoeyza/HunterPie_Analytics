from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.import_hunt import (
    ensure_monster,
    ensure_weapon,
    load_monster_names,
    parse_ts,
    poogie_to_payloads,
)
from app.models import Base, DpsSnapshot, Hunt, HuntPlayer, MonsterEvent


def make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def sample_doc(**over):
    doc = {
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
            "abnormalities": [{"id": "X", "activations": []}],
        }],
        "monsters": [{
            "id": 31, "variant": 5, "max_health": 18450.0, "crown": 0,
            "enrage": {"activations": [{
                "started_at": "2026-09-06T03:33:57.2555952Z",
                "finished_at": "2026-09-06T03:36:00.6975541Z"}]},
            "hunt_started_at": "2026-09-06T03:33:30.7334751Z",
            "hunt_finished_at": "2026-09-06T03:36:12.4631848Z",
            "hunt_type": 1, "health_steps": [],
        }],
        "hash": "5B0389D5685CA451",
    }
    doc.update(over)
    return doc


def test_parse_ts_handles_z_and_7_digits():
    assert parse_ts("2026-09-06T03:33:06.0749492Z") == datetime(2026, 9, 6, 3, 33, 6, 74949)


def test_payload_mapping():
    [(payload, warnings)] = poogie_to_payloads(sample_doc(), {31: "Tetranadon"},
                                               "hv", "gv")
    assert payload["quest_id_external"] == "5B0389D5685CA451"
    assert payload["_monster_name"] == "Tetranadon"
    assert (payload["quest_id"], payload["quest_stars"], payload["quest_level"]) == (543, 6, 1)
    assert (payload["monster_max_hp"], payload["monster_variant"]) == (18450.0, 5)
    assert payload["players"][0]["total_damage"] == 183.0
    assert payload["players"][0]["peak_dps"] == 126.0
    # cumulative snapshots incl. tail frame past finished_at (tolerated)
    assert [s["cumulative_damage"] for s in payload["snapshots"]] == [57.0, 183.0]
    assert payload["snapshots"][-1]["ts_offset_seconds"] > 176  # past finished_at
    assert payload["events"][0]["event_type"] == "enrage"
    # abnormalities are now imported
    assert len(payload["abnormalities"]) == 0  # sample doc has empty activations


def test_end_to_end_import_and_redup():
    from app.import_hunt import import_doc
    s = make_session()
    [(hunt, created, _)] = import_doc(s, sample_doc(), {31: "Tetranadon"}, "hv", "gv")
    assert created
    assert s.execute(select(Hunt)).scalar_one().id == hunt.id
    assert len(s.execute(select(HuntPlayer)).scalars().all()) == 1
    assert len(s.execute(select(DpsSnapshot)).scalars().all()) == 2
    assert len(s.execute(select(MonsterEvent)).scalars().all()) == 1
    assert s.get(HuntPlayer, (hunt.id, 1)).weapon_id == 6  # HuntingHorn enum 5 -> row 6
    # re-import dedups
    [(_, created2, _)] = import_doc(s, sample_doc(), {31: "Tetranadon"}, "hv", "gv")
    assert created2 is False
    assert len(s.execute(select(Hunt)).scalars().all()) == 1


def test_multi_monster_registers_each_monster():
    from app.import_hunt import import_doc
    doc = sample_doc()
    doc["monsters"] = [doc["monsters"][0],
                       {**doc["monsters"][0], "id": 1, "max_health": 18450.0}]
    payloads = poogie_to_payloads(doc, {}, "hv", "gv")
    assert len(payloads) == 2
    assert [p["monster_id"] for p, _ in payloads] == [31, 1]
    assert any("multi-monster" in w for _, ws in payloads for w in ws)
    # each monster hunt carries the full quest damage
    assert payloads[0][0]["players"][0]["total_damage"] == 183.0
    assert payloads[1][0]["players"][0]["total_damage"] == 183.0
    # full end-to-end: two hunts, idempotent re-import
    s = make_session()
    results = import_doc(s, doc, {}, "hv", "gv")
    assert [c for _, c, _ in results] == [True, True]
    assert len(s.execute(select(Hunt)).scalars().all()) == 2
    results2 = import_doc(s, doc, {}, "hv", "gv")
    assert [c for _, c, _ in results2] == [False, False]
    assert len(s.execute(select(Hunt)).scalars().all()) == 2


def test_environment_bystander_skipped():
    """A barely-touched second monster (1 HP sample at ~99% HP) is an
    environment bystander, not a quest target: only the real target
    registers. Empty HP data keeps the monster (older dumps)."""
    from app.import_hunt import import_doc
    doc = sample_doc()
    target = {**doc["monsters"][0], "health_steps": [
        {"percentage": 0.99, "time": "2026-09-06T03:33:30.7334751Z"},
        {"percentage": 0.12, "time": "2026-09-06T03:36:12.4631848Z"},
    ]}
    bystander = {**doc["monsters"][0], "id": 2, "health_steps": [
        {"percentage": 0.996, "time": "2026-09-06T03:34:00.0000000Z"},
    ]}
    # lightly damaged (never below 40%) also counts as a bystander
    grazed = {**doc["monsters"][0], "id": 8, "health_steps": [
        {"percentage": 0.99, "time": "2026-09-06T03:34:00.0000000Z"},
        {"percentage": 0.70, "time": "2026-09-06T03:35:00.0000000Z"},
    ]}
    doc["monsters"] = [target, bystander, grazed]
    payloads = poogie_to_payloads(doc, {}, "hv", "gv")
    assert len(payloads) == 1
    assert payloads[0][0]["monster_id"] == 31
    assert any("environment" in w for _, ws in payloads for w in ws)
    s = make_session()
    results = import_doc(s, doc, {}, "hv", "gv")
    assert len(results) == 1
    assert len(s.execute(select(Hunt)).scalars().all()) == 1


def test_bystander_threshold_is_40_percent():
    """HP floor: a monster scratched to 45% is a bystander, one down to 20%
    is a target. Sample count no longer matters (3 samples at 68% — the
    Guardian Anjanath case — is skipped)."""
    from app.import_hunt import import_doc
    doc = sample_doc()
    base = doc["monsters"][0]
    step = lambda frac: {"percentage": frac, "time": "2026-09-06T03:34:00.0000000Z"}
    scratched = {**base, "id": 8, "health_steps": [step(0.99), step(0.45)]}
    engaged = {**base, "id": 9, "health_steps": [step(0.99), step(0.20)]}
    splash = {**base, "id": 14, "health_steps": [step(0.997), step(0.85), step(0.685)]}
    doc["monsters"] = [scratched, engaged, splash]
    payloads = poogie_to_payloads(doc, {}, "hv", "gv")
    assert [p["monster_id"] for p, _ in payloads] == [9]


def test_quest_with_no_engagement_registers_nothing():
    """No monster HP below 40% (walked past everything): the quest is
    skipped entirely."""
    doc = sample_doc()
    base = doc["monsters"][0]
    step = lambda frac: {"percentage": frac, "time": "2026-09-06T03:34:00.0000000Z"}
    doc["monsters"] = [{**base, "id": 8, "health_steps": [step(0.99), step(0.80)]}]
    assert poogie_to_payloads(doc, {}, "hv", "gv") == []


def test_failed_quest_registers_despite_no_engagement():
    """Carted out (deaths >= max): the attempt registers even though no
    monster HP fell below 40%, stored with cleared=False."""
    from app.import_hunt import import_doc
    doc = sample_doc()
    doc["quest"] = {**doc["quest"], "deaths": 3, "max_deaths": 3}
    base = doc["monsters"][0]
    step = lambda frac: {"percentage": frac, "time": "2026-09-06T03:34:00.0000000Z"}
    doc["monsters"] = [{**base, "health_steps": [step(0.99), step(0.80)]}]
    [(payload, warnings)] = poogie_to_payloads(doc, {}, "hv", "gv")
    assert payload["cleared"] is False
    assert any("failed" in w for w in warnings)
    s = make_session()
    [(hunt, created, _)] = import_doc(s, doc, {}, "hv", "gv")
    assert created and hunt.cleared is False


def test_zero_stars_means_unknown():
    """The fork reports stars=0 when it doesn't know; no 0-star quests
    exist, so coerce to None instead of polluting filters."""
    doc = sample_doc()
    doc["quest"]["stars"] = 0
    [(payload, _)] = poogie_to_payloads(doc, {}, "hv", "gv")
    assert payload["quest_stars"] is None


def test_reference_helpers():
    s = make_session()
    assert ensure_weapon(s, 5) == 6
    assert ensure_weapon(s, 255) is None
    assert ensure_monster(s, 31, {}) == 31
    # explicit bad path falls back to the repo-bundled Wilds names
    # (so seeds/ import with real names on machines without HunterPie)
    bundled = load_monster_names("/nonexistent.xml")
    assert bundled[27] == "Arkveld" and bundled[31] == "Xu Wu"


def test_monster_names_use_wilds_section(tmp_path):
    xml = tmp_path / "en-us.xml"
    xml.write_text(
        "<GameData><Monsters>"
        '<Rise><Monster Id="31" String="Tetranadon" /></Rise>'
        '<Wilds><Monster Id="31" String="Xu Wu" /></Wilds>'
        "</Monsters></GameData>",
        encoding="utf-8",
    )
    assert load_monster_names(xml) == {31: "Xu Wu"}
