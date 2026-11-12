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


def test_linux_steam_roots_reads_libraryfolders(tmp_path):
    """Native Linux: the default Steam root plus extra library drives."""
    from app.import_hunt import _linux_steam_roots

    steam = tmp_path / ".steam" / "steam"
    (steam / "steamapps").mkdir(parents=True)
    extra = tmp_path / "Games"
    extra.mkdir()
    (steam / "steamapps" / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n  "0"\n  {{\n    "path" "{extra}"\n  }}\n}}\n',
        encoding="utf-8")

    roots = _linux_steam_roots(tmp_path)
    assert steam in roots
    assert extra in roots


def test_linux_hunterpie_candidates_cover_proton_guide_layout(tmp_path):
    """The Windows companion run via Proton dumps next to its exe."""
    from app.import_hunt import _linux_hunterpie_candidates

    paths = _linux_hunterpie_candidates(tmp_path)
    assert tmp_path / ".local/share/HunterPie/HuntExports" in paths
    assert tmp_path / "HunterPie/HuntExports" in paths


def test_prefix_hunterpie_candidates_find_installer_layout(tmp_path):
    from app.import_hunt import _prefix_hunterpie_candidates

    pfx = tmp_path / "compatdata" / "2246340" / "pfx"
    (pfx / "drive_c" / "Program Files" / "HunterPie" / "HuntExports").mkdir(
        parents=True)
    (pfx / "drive_c" / "users" / "steamuser" / "AppData" / "Local"
     / "HunterPie" / "HuntExports").mkdir(parents=True)

    paths = _prefix_hunterpie_candidates([pfx])
    assert pfx / "drive_c/Program Files/HunterPie/HuntExports" in paths
    assert (pfx / "drive_c/users/steamuser/AppData/Local/HunterPie/HuntExports"
            in paths)
    assert _prefix_hunterpie_candidates([tmp_path / "missing"]) == []


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


def _two_monster_doc():
    """Arkveld (target) + Guardian Rathalos (invader, not a target)."""
    doc = sample_doc()
    hunt_window = {
        "variant": None, "crown": 0, "enrage": {"activations": []},
        "ailments": [], "hunt_type": 1,
        "hunt_started_at": "2026-09-06T03:33:30.7334751Z",
        "hunt_finished_at": "2026-09-06T03:36:12.4631848Z",
    }
    doc["monsters"] = [
        {**hunt_window, "id": 27, "max_health": 20000.0, "is_target": True,
         "health_steps": [{"percentage": 0.2,
                           "time": "2026-09-06T03:35:00Z"}]},
        {**hunt_window, "id": 2, "max_health": 12000.0, "is_target": False,
         "health_steps": [{"percentage": 0.1,
                           "time": "2026-09-06T03:35:00Z"}]},
    ]
    return doc


def test_quest_targets_only_marks_non_targets_hidden():
    """Setting on: a non-target monster is imported hidden (Ignore-like),
    the target stays visible, and the quest is no longer a split quest."""
    payloads = poogie_to_payloads(_two_monster_doc(),
                                  {27: "Arkveld", 2: "Guardian Rathalos"},
                                  "hv", "gv", quest_targets_only=True)
    by_id = {p["monster_id"]: (p, w) for p, w in payloads}
    assert set(by_id) == {27, 2}
    target, target_notes = by_id[27]
    assert target["is_target"] is True
    assert "ignored" not in target
    extra, extra_notes = by_id[2]
    assert extra["is_target"] is False
    assert extra["ignored"] is True
    assert any("not a quest target" in w for w in extra_notes)
    assert not any("skipping" in w for w in target_notes + extra_notes)
    # one visible row -> not a split quest
    assert all(p["is_split_quest"] is False for p, _ in payloads)


def test_target_identity_exported_with_filter_off():
    """Target identity is stored even when the filter is off, so it can be
    toggled later; both monsters stay visible and the quest is split."""
    payloads = poogie_to_payloads(_two_monster_doc(),
                                  {27: "Arkveld", 2: "Guardian Rathalos"},
                                  "hv", "gv")
    by_id = {p["monster_id"]: p for p, _ in payloads}
    assert by_id[27]["is_target"] is True
    assert by_id[2]["is_target"] is False
    assert "ignored" not in by_id[2]
    assert all(p["is_split_quest"] is True for p, _ in payloads)


def test_quest_targets_only_without_target_identity_falls_back():
    """Mod-only dumps (and old companion builds) have no is_target: keep the
    previous behavior and report that the filter could not be applied."""
    [(payload, warnings)] = poogie_to_payloads(
        sample_doc(), {31: "Tetranadon"}, "hv", "gv", quest_targets_only=True)
    assert "is_target" not in payload
    assert "ignored" not in payload
    assert any("quest-objective filter skipped" in w for w in warnings)


def test_ailment_activations_become_events():
    """Fork `monsters[].ailments[]` becomes `ailment.<name>` spans; duplicate
    slots and enrage/unknown ids never reach monster_events."""
    doc = sample_doc()
    doc["monsters"][0]["ailments"] = [
        {"id": "AILMENT_POISON", "activations": [
            {"started_at": "2026-09-06T03:33:20.0749492Z",
             "finished_at": "2026-09-06T03:33:44.0749492Z"},
            {"started_at": "2026-09-06T03:33:50.0749492Z",
             "finished_at": None},
        ]},
        # Second memory slot for the same status: the identical window is
        # dropped (monster_events is unique on type + start).
        {"id": "AILMENT_POISON", "activations": [
            {"started_at": "2026-09-06T03:33:20.0749492Z",
             "finished_at": "2026-09-06T03:33:44.0749492Z"},
        ]},
        {"id": "AILMENT_STUN", "activations": [
            {"started_at": "2026-09-06T03:34:00.0749492Z",
             "finished_at": "2026-09-06T03:34:10.0749492Z"},
        ]},
        {"id": "AILMENT_ENRAGE", "activations": [
            {"started_at": "2026-09-06T03:33:30.0749492Z",
             "finished_at": "2026-09-06T03:33:40.0749492Z"},
        ]},
        {"id": "AILMENT_UNKNOWN", "activations": []},
    ]
    [(payload, _)] = poogie_to_payloads(doc, {31: "Tetranadon"}, "hv", "gv")
    events = [(e["event_type"], e["start_offset_seconds"],
               e["end_offset_seconds"]) for e in payload["events"]]
    assert events.count(("ailment.poison", 14.0, 38.0)) == 1
    assert ("ailment.poison", 44.0, None) in events
    assert ("ailment.stun", 54.0, 64.0) in events
    assert not any(t.startswith("ailment.enrage") for t, *_ in events)
    assert not any(t.startswith("ailment.unknown") for t, *_ in events)


def test_supporter_flag_passed_through():
    """REFramework dumps tag CPU companions is_supporter; the importer must
    carry it through (previously hardcoded False)."""
    doc = sample_doc(players=[
        {"name": "Isi", "weapon": 5, "damages": [
            {"damage": 100.0, "dealt_at": "2026-09-06T03:36:00Z"}]},
        {"name": "NPC 5", "weapon": 5, "is_supporter": True, "damages": []},
    ])
    [(payload, _)] = poogie_to_payloads(doc, {31: "Tetranadon"}, "hv", "gv")
    by_name = {p["display_name"]: p for p in payload["players"]}
    assert by_name["NPC 5"]["is_supporter"] is True
    assert by_name["Isi"]["is_supporter"] is False


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


def test_split_quest_awards_attach_to_primary_only():
    """Quest-level awards/highlights live on the first (primary) monster hunt
    only, so a split quest can't double-count them across sibling rows."""
    doc = sample_doc(source="reframework",
                     awards_meta=[{"id": 4, "name": "Established Hunter",
                                   "unit": 0}])
    step = lambda frac: {"percentage": frac,
                         "time": "2026-09-06T03:34:00.0000000Z"}
    base = doc["monsters"][0]
    doc["monsters"] = [
        {**base, "id": 31, "health_steps": [step(0.99), step(0.10)]},
        {**base, "id": 1, "health_steps": [step(0.99), step(0.10)]},
    ]
    doc["players"][0]["awards"] = [{"id": 4, "count": 900}]
    doc["players"][0]["weapon_name"] = "War Conga"
    payloads = poogie_to_payloads(doc, {31: "Arkveld", 1: "Blangonga"}, "hv", "gv")
    assert len(payloads) == 2
    primary, sibling = payloads[0][0], payloads[1][0]
    assert primary["players"][0]["awards"] == [{"id": 4, "count": 900}]
    assert primary["awards_meta"]
    assert sibling["players"][0]["awards"] == []
    assert sibling["awards_meta"] is None
    # weapon_name is per-hunt (local player), so it stays on every sibling
    assert sibling["players"][0]["weapon_name"] == "War Conga"


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
    doc = sample_doc()
    base = doc["monsters"][0]
    step = lambda frac: {"percentage": frac, "time": "2026-09-06T03:34:00.0000000Z"}
    scratched = {**base, "id": 8, "health_steps": [step(0.99), step(0.45)]}
    engaged = {**base, "id": 9, "health_steps": [step(0.99), step(0.20)]}
    splash = {**base, "id": 14, "health_steps": [step(0.997), step(0.85), step(0.685)]}
    doc["monsters"] = [scratched, engaged, splash]
    payloads = poogie_to_payloads(doc, {}, "hv", "gv")
    assert [p["monster_id"] for p, _ in payloads] == [9]


def test_quest_target_always_included_even_without_engagement():
    """A successful speedrun target may never enrage or apply an ailment.
    Target identity must keep it even at high HP."""
    doc = sample_doc()
    base = doc["monsters"][0]
    step = lambda frac: {"percentage": frac, "time": "2026-09-06T03:34:00.0000000Z"}
    doc["monsters"] = [{**base, "id": 31, "is_target": True,
                        "enrage": {"activations": []}, "ailments": [],
                        "health_steps": [step(0.99)]}]
    payloads = poogie_to_payloads(doc, {}, "hv", "gv")
    assert [p["monster_id"] for p, _ in payloads] == [31]


def test_target_info_keeps_only_targets_and_heavy_non_targets():
    """Once the dump has target identity, enrage alone must not smuggle in a
    turf-war bystander. Non-targets need >60% HP loss (HP below 40%)."""
    doc = sample_doc()
    base = doc["monsters"][0]
    step = lambda frac: {"percentage": frac, "time": "2026-09-06T03:34:00.0000000Z"}
    target = {**base, "id": 31, "is_target": True,
              "health_steps": [step(0.99)]}
    enraged_bystander = {**base, "id": 2, "is_target": False,
                         "health_steps": [step(0.995)]}
    heavy = {**base, "id": 9, "is_target": False,
             "health_steps": [step(0.99), step(0.39)]}
    light = {**base, "id": 14, "is_target": False,
             "health_steps": [step(0.99), step(0.50)]}
    doc["monsters"] = [target, enraged_bystander, heavy, light]
    payloads = poogie_to_payloads(doc, {}, "hv", "gv")
    assert [p["monster_id"] for p, _ in payloads] == [31, 9]
    assert any("not a quest target" in w for _, ws in payloads for w in ws)


def test_failed_hunt_with_target_info_uses_the_same_engagement_rule():
    doc = sample_doc()
    doc["quest"] = {**doc["quest"], "cleared": False,
                    "deaths": 0, "max_deaths": 3}
    base = doc["monsters"][0]
    step = lambda frac: {"percentage": frac, "time": "2026-09-06T03:34:00.0000000Z"}
    target = {**base, "id": 31, "is_target": True,
              "health_steps": [step(0.99)]}
    heavy = {**base, "id": 9, "is_target": False,
             "health_steps": [step(0.99), step(0.39)]}
    light = {**base, "id": 14, "is_target": False,
             "health_steps": [step(0.99), step(0.50)]}
    doc["monsters"] = [target, heavy, light]
    payloads = poogie_to_payloads(doc, {}, "hv", "gv")
    assert [p["monster_id"] for p, _ in payloads] == [31, 9]
    assert all(p["cleared"] is False for p, _ in payloads)


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


def test_failed_quest_explicit_cleared_without_carts():
    """Time-up failures carry cleared=False with deaths < max_deaths. The
    explicit outcome must win so the attempt still registers as failed."""
    from app.import_hunt import import_doc
    doc = sample_doc()
    doc["quest"] = {**doc["quest"], "cleared": False, "deaths": 0, "max_deaths": 3}
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


def test_quest_result_fail_is_not_cleared():
    from app.import_hunt import _quest_failed
    assert _quest_failed({"quest": {"result": "fail"}}) is True
    assert _quest_failed({"quest": {"result": "quit"}}) is True
    assert _quest_failed({"quest": {"cleared": False}}) is True
    # explicit success wins over a stale deaths counter
    assert _quest_failed({"quest": {"result": "success", "deaths": 3,
                                    "max_deaths": 3}}) is False
    # explicit cleared=True also wins over a stale deaths counter
    assert _quest_failed({"quest": {"cleared": True, "deaths": 3,
                                    "max_deaths": 3}}) is False
    # legacy dumps: carts only
    assert _quest_failed({"quest": {"deaths": 3, "max_deaths": 3}}) is True
    assert _quest_failed({"quest": {"deaths": 1, "max_deaths": 3}}) is False
