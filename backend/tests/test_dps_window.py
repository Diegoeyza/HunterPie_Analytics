"""DPS window setting: engagement (first->last hit) vs quest (first hit->kill)."""
import os
import tempfile
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app import settings
from app.db import dispose_engine, init_db, make_session
from app.engagement import (
    batch_capped_damage_s,
    batch_engagement_s,
    player_engagement_s,
)
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


def test_quest_clock_shorter_than_snapshots_freezes_there():
    """Cross-source rebases can leave quest_time shorter than the snapshot
    span: quest mode still freezes at the quest clock with damage as of
    that point (HunterPie shows damage accumulated by quest end over the
    same window), it does not stretch to the late-flushed last hit."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        # snapshots span 10->50, but the quest clock claims only 30s
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=30.0,
                           external="dpsw-6"))
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="quest")
        assert got[(hid, 1)] == 20.0  # quest_end(30) - first(10)
        cap = batch_capped_damage_s(s, hunts, [(hid, 1)], window="quest")
        assert cap[(hid, 1)] == 300.0  # damage as of the 30s snapshot
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


def test_quest_capped_damage_excludes_post_freeze_tail():
    """Hunt 1006 shape: capture at 60 (last HP sample, no kill), quest clock
    100, damage flushed to 90. Quest DPS = damage-as-of-60 / (60 - first),
    matching the meter, which froze at capture."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=100.0,
                           external="dpsw-9",
                           hp_steps=[{"ts_offset_seconds": 20.0,
                                      "hp_fraction": 0.5},
                                     {"ts_offset_seconds": 60.0,
                                      "hp_fraction": 0.13}]),
        )
        hunts = {hid: s.get(Hunt, hid)}
        # snapshots run 10->50 in the helper; extend the tail past the
        # freeze with a late-flushed hit worth 1000 at t=90.
        from app.models import DpsSnapshot
        last = s.execute(
            select(func.max(DpsSnapshot.ts_offset_seconds))
            .where(DpsSnapshot.hunt_id == hid)).scalar()
        assert last == 50.0
        s.add(DpsSnapshot(hunt_id=hid, player_id=1,
                          ts_offset_seconds=90.0,
                          cumulative_damage=1500.0, instant_dps=5.0))
        s.flush()
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="quest")
        assert got[(hid, 1)] == 50.0  # freeze(60) - first(10)
        cap = batch_capped_damage_s(s, hunts, [(hid, 1)], window="quest")
        assert cap[(hid, 1)] == 500.0  # tail excluded, not 1500
        assert player_engagement_s(
            s, hid, 1, window="quest") == 50.0
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_quest_stale_freeze_falls_back_to_engagement():
    """HP tracker died early (last sample 67, damage runs to 152): the
    freeze would collapse the numerator to ~nothing, so quest mode falls
    back to engagement and the capped dict stays empty (full totals)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        from app.models import DpsSnapshot
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=587.0,
                           external="dpsw-10",
                           hp_steps=[{"ts_offset_seconds": 7.0,
                                      "hp_fraction": 1.0},
                                     {"ts_offset_seconds": 67.0,
                                      "hp_fraction": 0.25}]),
        )
        # stretch Isi's damage to 152 (SOS shape: freeze 67 << last 152)
        s.add(DpsSnapshot(hunt_id=hid, player_id=1,
                          ts_offset_seconds=152.0,
                          cumulative_damage=23385.0, instant_dps=5.0))
        s.flush()
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="quest")
        assert got[(hid, 1)] == 142.0  # engagement: 152 - 10
        cap = batch_capped_damage_s(s, hunts, [(hid, 1)], window="quest")
        assert cap == {}
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_capped_damage_empty_in_engagement_mode():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=100.0,
                           external="dpsw-11"))
        hunts = {hid: s.get(Hunt, hid)}
        assert batch_capped_damage_s(
            s, hunts, [(hid, 1)], window="engagement") == {}
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)
