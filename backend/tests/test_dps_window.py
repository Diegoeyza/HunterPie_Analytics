"""DPS window setting: engagement (first->last hit) vs quest (first hit->quest end)."""
import os
import tempfile
from datetime import datetime, timedelta

from app import settings
from app.db import dispose_engine, init_db, make_session
from app.engagement import batch_engagement_s, player_engagement_s
from app.ingest import upsert_hunt
from app.models import Hunt, Monster, Weapon


def _payload(start, quest_time=100.0, external="dpsw-1", damage_per_hit=100.0,
             hp_steps=None, cleared=True):
    snaps = [{"display_name": "Isi", "ts_offset_seconds": 10.0 + 10.0 * k,
              "cumulative_damage": damage_per_hit * (k + 1),
              "instant_dps": 10.0}
             for k in range(5)]  # first=10, last=50
    return {
        "quest_id_external": external, "monster_id": 31,
        "_monster_name": "Xu Wu",
        "started_at": start, "ended_at": start + timedelta(seconds=quest_time or 60),
        "quest_time_seconds": quest_time, "cart_count": 0, "cleared": True,
        "hunterpie_version": "t", "game_version": "g", "source": "hunterpie",
        "players": [{"display_name": "Isi", "weapon_id": 6,
                     "total_damage": damage_per_hit * 5, "peak_dps": 50.0,
                     "is_supporter": False}],
        "snapshots": snaps, "player_health": [],
        "hp_steps": hp_steps or [], "cleared": cleared,
    }


def _seeded_session(path, payload):
    init_db(path)
    s = make_session(path)
    s.add_all([Monster(id=31, name="Xu Wu"),
               Weapon(id=6, name="HuntingHorn", weapon_type="HuntingHorn")])
    s.flush()
    hunt, _, _ = upsert_hunt(s, payload)
    return s, hunt.id


def test_engagement_window_is_first_to_last():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=100.0))
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="engagement")
        assert got[(hid, 1)] == 40.0  # last(50) - first(10)
        assert player_engagement_s(s, hid, 1, window="engagement") == 40.0
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_quest_window_ends_at_quest_clock():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=100.0,
                           external="dpsw-2"))
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="quest")
        assert got[(hid, 1)] == 90.0  # quest_end(100) - first(10)
        assert player_engagement_s(s, hid, 1, window="quest") == 90.0
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_quest_window_falls_back_to_ended_at():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        p = _payload(datetime(2026, 9, 6, 3, 0), quest_time=None,
                     external="dpsw-3")
        p["ended_at"] = p["started_at"] + timedelta(seconds=80)
        s, hid = _seeded_session(path, p)
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="quest")
        assert got[(hid, 1)] == 70.0  # ended_at(80) - first(10)
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_quest_end_before_first_hit_falls_back():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=5.0,
                           external="dpsw-4"))
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="quest")
        assert got[(hid, 1)] == 40.0  # quest clock unusable -> engagement
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_window_defaults_to_setting(monkeypatch, tmp_path):
    monkeypatch.setenv("HUNTS_DB", str(tmp_path / "db" / "hunts.db"))
    settings.save_settings({"export_dirs": [], "dps_window": "quest"})
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=100.0,
                           external="dpsw-5"))
        hunts = {hid: s.get(Hunt, hid)}
        assert batch_engagement_s(s, hunts, [(hid, 1)])[(hid, 1)] == 90.0
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_quest_clock_shorter_than_snapshots_never_inflates():
    """Cross-source rebases can leave quest_time shorter than the snapshot
    span: quest mode must fall back to the hunter's own last hit, so it
    only ever dilutes DPS, never inflates it."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        # snapshots span 10->50, but the quest clock claims only 30s
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=30.0,
                           external="dpsw-6"))
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="quest")
        assert got[(hid, 1)] == 40.0
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_quest_window_freezes_at_kill_not_quest_end():
    """HunterPie stops the timer when the monster goes down: carving/return
    must not dilute DPS. Kill at 60, quest clock 100, snapshots 10->50."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        hp = [{"ts_offset_seconds": 20.0, "hp_fraction": 0.5},
              {"ts_offset_seconds": 60.0, "hp_fraction": 0.0}]
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=100.0,
                           external="dpsw-7", hp_steps=hp))
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="quest")
        assert got[(hid, 1)] == 50.0  # kill(60) - first(10), not 100 - 10
        assert player_engagement_s(s, hid, 1, window="quest") == 50.0
        # engagement mode unaffected by the kill record
        assert batch_engagement_s(
            s, hunts, [(hid, 1)], window="engagement")[(hid, 1)] == 40.0
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_quest_window_failed_hunt_ignores_partial_kill():
    """One target down then the quest fails: the meter runs to the fail,
    not the first kill. No 0-fallback to the early kill."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        hp = [{"ts_offset_seconds": 60.0, "hp_fraction": 0.0},
              {"ts_offset_seconds": 90.0, "hp_fraction": 0.4}]
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=100.0,
                           external="dpsw-8", hp_steps=hp, cleared=False))
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="quest")
        assert got[(hid, 1)] == 80.0  # last HP(90) - first(10)
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)
