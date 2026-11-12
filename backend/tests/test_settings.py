"""User settings persistence: fail-soft reads + atomic writes."""
from pathlib import Path

from app import settings


def test_settings_path_follows_hunts_db(monkeypatch, tmp_path):
    monkeypatch.setenv("HUNTS_DB", str(tmp_path / "db" / "hunts.db"))
    assert settings.settings_path() == tmp_path / "db" / "config.json"


def test_settings_path_defaults_to_user_data(monkeypatch, tmp_path):
    assert settings.settings_path() == tmp_path / "config.json"


def test_missing_settings_is_empty(tmp_path):
    assert settings.load_settings(tmp_path / "missing.json") == {
        "export_dirs": [], "dps_window": "quest", "quest_targets_only": False,
        "quest_targets_backfilled": False}


def test_roundtrip_export_dirs(tmp_path):
    path = tmp_path / "config.json"
    settings.save_settings({"export_dirs": ["C:/MO2/overwrite"]}, path)

    assert settings.load_settings(path) == {
        "export_dirs": ["C:/MO2/overwrite"], "dps_window": "quest",
        "quest_targets_only": False,
        "quest_targets_backfilled": False}
    assert settings.configured_export_dirs(path) == [Path("C:/MO2/overwrite")]


def test_corrupt_settings_falls_back_to_empty(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")

    assert settings.load_settings(path) == {
        "export_dirs": [], "dps_window": "quest", "quest_targets_only": False,
        "quest_targets_backfilled": False}


def test_non_list_export_dirs_ignored(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"export_dirs": "oops"}', encoding="utf-8")

    assert settings.load_settings(path) == {
        "export_dirs": [], "dps_window": "quest", "quest_targets_only": False,
        "quest_targets_backfilled": False}


def test_non_string_entries_dropped(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"export_dirs": ["C:/ok", 3, null]}', encoding="utf-8")

    assert settings.load_settings(path) == {
        "export_dirs": ["C:/ok"], "dps_window": "quest",
        "quest_targets_only": False,
        "quest_targets_backfilled": False}


def test_dps_window_defaults_to_quest(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"export_dirs": []}', encoding="utf-8")

    assert settings.dps_window(path) == "quest"


def test_dps_window_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    settings.save_settings(
        {"export_dirs": [], "dps_window": "quest", "quest_targets_only": False,
        "quest_targets_backfilled": False}, path)

    assert settings.load_settings(path) == {
        "export_dirs": [], "dps_window": "quest", "quest_targets_only": False,
        "quest_targets_backfilled": False}
    assert settings.dps_window(path) == "quest"


def test_dps_window_invalid_falls_back(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"dps_window": "bogus"}', encoding="utf-8")

    assert settings.dps_window(path) == "quest"


def test_quest_targets_only_defaults_off(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"export_dirs": []}', encoding="utf-8")

    assert settings.quest_targets_only(path) is False


def test_quest_targets_only_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    settings.save_settings(
        {"export_dirs": [], "dps_window": "quest", "quest_targets_only": True},
        path)

    assert settings.load_settings(path)["quest_targets_only"] is True
    assert settings.quest_targets_only(path) is True


def test_quest_targets_only_rejects_non_booleans(tmp_path):
    """A hand-edited "false"/1 must not read as truthy."""
    path = tmp_path / "config.json"
    path.write_text('{"quest_targets_only": "false"}', encoding="utf-8")

    assert settings.quest_targets_only(path) is False


def test_quest_targets_backfilled_marker(tmp_path):
    """Bookkeeping marker survives a settings save and keeps preferences."""
    path = tmp_path / "config.json"
    assert settings.quest_targets_backfilled(path) is False
    settings.save_settings({"export_dirs": [], "dps_window": "quest",
                            "quest_targets_only": True}, path)
    settings.mark_quest_targets_backfilled(path)

    assert settings.quest_targets_backfilled(path) is True
    assert settings.quest_targets_only(path) is True
