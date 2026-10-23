"""DPS window setting: engagement (own first->last hit) vs quest (own first->party last)."""
import os
import tempfile
from datetime import datetime, timedelta

from app import settings
from app.db import dispose_engine, init_db, make_session
from app.engagement import batch_engagement_s, player_engagement_s
from app.models import DpsSnapshot, HuntPlayer, Player
from app.ingest import upsert_hunt
from app.models import Hunt, Monster, Weapon  # noqa: F401


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


def test_quest_window_ends_at_party_last_hit():
    """Single hunter: the party's last hit is their own — the quest clock
    is ignored, so a short clock never inflates DPS."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=100.0,
                           external="dpsw-2"))
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="quest")
        assert got[(hid, 1)] == 40.0  # party last(50) - first(10)
        assert player_engagement_s(s, hid, 1, window="quest") == 40.0
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_quest_window_split_end_shared_by_party():
    """Hunt 1008 shape: one hunter stops at 378, the other fights to 411.
    Quest mode ends BOTH windows at the party's last hit, from each
    hunter's own start — the overlay divides each damage by
    (results - own first). Engagement keeps per-hunter ends."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=393.8,
                           external="dpsw-2b"))
        uni = Player(display_name="Uni",
                     first_seen_at=datetime(2026, 9, 6, 3, 0))
        s.add(uni)
        s.flush()
        s.add(HuntPlayer(hunt_id=hid, player_id=uni.id, weapon_id=6,
                         total_damage=52856.0, peak_dps=0.0,
                         is_supporter=False))
        s.add_all([
            DpsSnapshot(hunt_id=hid, player_id=uni.id,
                        ts_offset_seconds=55.0, cumulative_damage=100.0,
                        instant_dps=10.0),
            DpsSnapshot(hunt_id=hid, player_id=uni.id,
                        ts_offset_seconds=378.7, cumulative_damage=52856.0,
                        instant_dps=10.0),
        ])
        s.flush()
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(
            s, hunts, [(hid, 1), (hid, uni.id)], window="quest")
        assert got[(hid, 1)] == 368.7  # party last(378.7) - Isi first(10)
        assert got[(hid, uni.id)] == 323.7  # 378.7 - Uni first(55)
        eng = batch_engagement_s(
            s, hunts, [(hid, 1), (hid, uni.id)], window="engagement")
        assert eng[(hid, 1)] == 40.0  # own span only
        assert eng[(hid, uni.id)] == 323.7
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_quest_window_without_snapshots_falls_back_to_duration():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        p = _payload(datetime(2026, 9, 6, 3, 0), quest_time=None,
                     external="dpsw-3")
        p["ended_at"] = p["started_at"] + timedelta(seconds=80)
        p["snapshots"] = []
        s, hid = _seeded_session(path, p)
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="quest")
        assert got[(hid, 1)] == 80.0  # no damage data -> hunt duration
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_quest_clock_earlier_than_snapshots_is_ignored():
    """Cross-source rebases can leave quest_time shorter than the snapshot
    span: quest mode trusts the damage stream (party last hit), not the
    short clock."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=5.0,
                           external="dpsw-4"))
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="quest")
        assert got[(hid, 1)] == 40.0  # party last(50) - first(10)
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
        assert batch_engagement_s(s, hunts, [(hid, 1)])[(hid, 1)] == 40.0
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_quest_clock_shorter_than_snapshots_uses_damage_stop():
    """Cross-source rebases can leave quest_time shorter than the snapshot
    span: quest mode trusts the damage stream (the meter's timer ran while
    damage flowed), it does not shrink to the short clock."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        # snapshots span 10->50, but the quest clock claims only 30s
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=30.0,
                           external="dpsw-6"))
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="quest")
        assert got[(hid, 1)] == 40.0  # party last(50) - first(10)
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_quest_window_ignores_kill_hp_stop():
    """HP tracking dies before the quest ends (hunt 1008: HP stops at 67
    while damage runs to 152): quest mode still ends at the party's last
    hit. The overlay's timer runs to the results screen, not to HP
    silence — a kill record must not shrink the window either."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        hp = [{"ts_offset_seconds": 7.0, "hp_fraction": 1.0},
              {"ts_offset_seconds": 60.0, "hp_fraction": 0.0},
              {"ts_offset_seconds": 67.0, "hp_fraction": 0.25}]
        s, hid = _seeded_session(
            path, _payload(datetime(2026, 9, 6, 3, 0), quest_time=587.0,
                           external="dpsw-7", hp_steps=hp))
        # damage runs past every HP signal (SOS shape: freeze 67 << last)
        s.add(DpsSnapshot(hunt_id=hid, player_id=1,
                          ts_offset_seconds=152.0,
                          cumulative_damage=23385.0, instant_dps=5.0))
        s.flush()
        hunts = {hid: s.get(Hunt, hid)}
        got = batch_engagement_s(s, hunts, [(hid, 1)], window="quest")
        assert got[(hid, 1)] == 142.0  # party last(152) - first(10)
        assert player_engagement_s(s, hid, 1, window="quest") == 142.0
        # engagement mode agrees here (single hunter, own last is the max)
        assert batch_engagement_s(
            s, hunts, [(hid, 1)], window="engagement")[(hid, 1)] == 142.0
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)


def test_quest_window_failed_hunt_uses_damage_stop():
    """Failed hunts have no meaningful HP freeze: the window ends at the
    party's last hit like everywhere else."""
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
        assert got[(hid, 1)] == 40.0  # party last(50) - first(10)
    finally:
        s.close()
        dispose_engine(path)
        os.unlink(path)
