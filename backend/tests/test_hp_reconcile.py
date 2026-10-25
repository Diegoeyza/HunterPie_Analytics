"""HP identity reconciliation (Gog-siege faint mislabeled Light not Diego).

The mod keys HP samples by control slot but names them by compact-list
position; when the orders disagree the dump swaps two hunters. Repair
fires only on physical impossibility (dealing damage straight through
your own 0-HP readings with instant full recovery) plus a unique silent
hunter covering that window. Everything else warns or stays put.
"""
from datetime import datetime

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from app.db import _on_connect
from app.engagement import batch_engagement_s
from app.ingest import reconcile_hp_identity, upsert_hunt
from app.models import (
    Base,
    Hunt,
    Monster,
    Player,
    PlayerHealthStep,
    Weapon,
)


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    event.listen(engine, "connect", _on_connect)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, future=True)()
    s.add(Monster(name="Gogmazios", species="Elder Dragon"))
    s.add(Weapon(name="Great Sword", weapon_type="GS"))
    s.commit()
    return s


def _ticks(name, spans, dmg=100.0):
    """Damage snapshots covering [(start, end)] ranges at ~7s cadence."""
    out = []
    cum = 0.0
    for lo, hi in spans:
        t = float(lo)
        while t <= hi:
            cum += dmg
            out.append({"display_name": name,
                        "ts_offset_seconds": round(t, 1),
                        "cumulative_damage": cum, "instant_dps": 10.0})
            t += 7.0
    return out


def _hp(name, points):
    """Player-HP samples from [(ts, fraction)] with flat red/max."""
    return [{"display_name": name, "ts_offset_seconds": float(t),
             "hp_fraction": float(h), "red_fraction": 0.5, "max_hp": 150.0}
            for t, h in points]


def _payload(snaps, health):
    return {
        "monster_id": 1,
        "started_at": datetime(2026, 2, 1, 12, 0, 0),
        "ended_at": datetime(2026, 2, 1, 12, 10, 0),
        "quest_time_seconds": 600,
        "cleared": True,
        "hunterpie_version": "2.14.0",
        "game_version": "1.40.0.0",
        "players": [
            {"display_name": "Light", "weapon_id": 1,
             "total_damage": 5000, "peak_dps": 100},
            {"display_name": "Diego", "weapon_id": 1,
             "total_damage": 5000, "peak_dps": 100},
        ],
        "snapshots": snaps, "player_health": health,
        "hp_steps": [], "events": [],
    }


def _hp_by_name(s, hid):
    rows = s.execute(
        select(Player.display_name, PlayerHealthStep.ts_offset_seconds,
               PlayerHealthStep.hp_fraction)
        .join(PlayerHealthStep,
              PlayerHealthStep.player_id == Player.id)
        .where(PlayerHealthStep.hunt_id == hid)
        .order_by(Player.display_name,
                   PlayerHealthStep.ts_offset_seconds)).all()
    out = {}
    for name, ts, hp in rows:
        out.setdefault(name, []).append((ts, hp))
    return out


def test_swap_impossible_faint_to_silent_hunter():
    """1022 shape: Light's HP hits 0 at 54/59 while Light keeps dealing
    damage, and Diego goes silent 47->103. The series are swapped."""
    s = _session()
    snaps = (_ticks("Light", [(45, 120)]) + _ticks("Diego", [(38, 46), (103, 120)]))
    health = (_hp("Light", [(47, 1.0), (52, 0.54), (54, 0.0), (59, 0.0),
                             (60, 1.0), (70, 1.0)])
              + _hp("Diego", [(47, 1.0), (60, 1.0), (70, 1.0)]))
    hunt, created, warnings = upsert_hunt(s, _payload(snaps, health))
    assert created is True
    assert any("hp-identity-fixed" in w for w in warnings), warnings
    by_name = _hp_by_name(s, hunt.id)
    assert min(h for _, h in by_name["Light"]) == 1.0
    assert min(h for _, h in by_name["Diego"]) == 0.0
    # DPS still divides each total by the shared quest end.
    eng = batch_engagement_s(
        s, {hunt.id: hunt}, [(hunt.id, 1), (hunt.id, 2)], window="quest")
    # shared quest end from each hunter's own start (38 vs 45)
    assert eng[(hunt.id, 1)] + 45.0 == eng[(hunt.id, 2)] + 38.0
    s.close()


def test_real_faint_inside_own_gap_untouched():
    """Consistent faint: zeros inside the hunter's own long damage gap are
    left alone, even with fast-looking recovery."""
    s = _session()
    snaps = (_ticks("Light", [(45, 120)]) + _ticks("Diego", [(45, 46), (103, 120)]))
    health = (_hp("Light", [(47, 1.0), (60, 1.0), (70, 1.0)])
              + _hp("Diego", [(40, 1.0), (46, 0.5), (47, 0.0), (52, 0.0),
                               (70, 0.5), (103, 1.0)]))
    hunt, created, warnings = upsert_hunt(s, _payload(snaps, health))
    assert created is True
    assert warnings == [], warnings
    by_name = _hp_by_name(s, hunt.id)
    assert min(h for _, h in by_name["Diego"]) == 0.0
    s.close()


def test_artifact_without_decline_only_warns():
    """1.0->0 cliff with no taking-damage ramp is a sampling artifact:
    flagged, never reassigned — even with a silent hunter around."""
    s = _session()
    snaps = (_ticks("Light", [(45, 120)]) + _ticks("Diego", [(45, 120)]))
    health = (_hp("Light", [(47, 1.0), (52, 1.0), (54, 0.0), (59, 0.0),
                             (60, 1.0)])
              + _hp("Diego", [(47, 1.0), (60, 1.0)]))
    hunt, created, warnings = upsert_hunt(s, _payload(snaps, health))
    assert created is True
    assert any("hp-artifact?" in w for w in warnings), warnings
    assert not any("hp-identity-fixed" in w for w in warnings)
    by_name = _hp_by_name(s, hunt.id)
    assert min(h for _, h in by_name["Light"]) == 0.0  # untouched
    s.close()


def test_ambiguous_complements_only_warn():
    """Impossible zeros but two silent hunters: no unique owner, so the
    series stay put and the hunt is flagged."""
    s = _session()
    snaps = (_ticks("Light", [(45, 120)])
             + _ticks("Diego", [(38, 46), (70, 120)])
             + _ticks("Mina", [(38, 46), (80, 120)]))
    health = (_hp("Light", [(47, 1.0), (52, 0.54), (54, 0.0), (59, 0.0),
                             (60, 1.0)])
              + _hp("Diego", [(47, 1.0), (60, 1.0)])
              + _hp("Mina", [(47, 1.0), (60, 1.0)]))
    payload = _payload(snaps, health)
    payload["players"].append(
        {"display_name": "Mina", "weapon_id": 1,
         "total_damage": 1000, "peak_dps": 20})
    hunt, created, warnings = upsert_hunt(s, payload)
    assert created is True
    assert any("2 silent candidates" in w for w in warnings), warnings
    assert not any("hp-identity-fixed" in w for w in warnings)
    by_name = _hp_by_name(s, hunt.id)
    assert min(h for _, h in by_name["Light"]) == 0.0  # untouched
    s.close()


def test_late_joiner_gap_does_not_attract_swap():
    """A hunter whose damage starts after the window (late join) is not an
    interior gap, so an impossible zero-run with no other candidate warns
    instead of swapping onto the newcomer."""
    s = _session()
    snaps = (_ticks("Light", [(45, 120)])
             + _ticks("Diego", [(100, 120)]))
    health = (_hp("Light", [(47, 1.0), (52, 0.54), (54, 0.0), (59, 0.0),
                             (60, 1.0)])
              + _hp("Diego", [(100, 1.0), (110, 1.0)]))
    payload = _payload(snaps, health)
    payload["players"][1] = {"display_name": "Diego", "weapon_id": 1,
                              "total_damage": 1000, "peak_dps": 20}
    # Diego's ticks start at 100: his "gap" is join delay, not a faint.
    hunt, created, warnings = upsert_hunt(s, payload)
    assert created is True
    assert any("0 silent candidates" in w for w in warnings), warnings
    assert not any("hp-identity-fixed" in w for w in warnings)
    s.close()


def test_reconcile_is_idempotent():
    """Running twice converges: the second pass finds no contradiction."""
    from app.ingest import reconcile_hp_identity
    s = _session()
    snaps = (_ticks("Light", [(45, 120)])
             + _ticks("Diego", [(38, 46), (103, 120)]))
    health = (_hp("Light", [(47, 1.0), (52, 0.54), (54, 0.0), (59, 0.0),
                             (60, 1.0), (70, 1.0)])
              + _hp("Diego", [(47, 1.0), (60, 1.0), (70, 1.0)]))
    hunt, _, warnings = upsert_hunt(s, _payload(snaps, health))
    assert any("hp-identity-fixed" in w for w in warnings)
    again = reconcile_hp_identity(s, hunt)
    assert again == [], again
    s.close()


def test_boundary_tick_does_not_suppress_true_swap():
    """A final tick landing ~0.1s after the first zero (the downing moment
    on a 5s HP poll cadence) must not veto a swap when the labeled hunter
    keeps dealing through the window and the silent hunter's gap starts
    at the zero."""
    s = _session()
    snaps = (_ticks("Light", [(45, 120)]) + _ticks("Diego", [(38, 52), (110, 120)]))
    # Extra boundary tick right at the zero start, plus through-window
    # activity afterwards: Light fought while "his" HP read 0.
    snaps.append({"display_name": "Light", "ts_offset_seconds": 54.1,
                  "cumulative_damage": 9999.0, "instant_dps": 10.0})
    health = (_hp("Light", [(47, 1.0), (52, 0.54), (54, 0.0), (59, 0.0),
                             (60, 1.0), (70, 1.0)])
              + _hp("Diego", [(47, 1.0), (60, 1.0), (70, 1.0)]))
    hunt, created, warnings = upsert_hunt(s, _payload(snaps, health))
    assert created is True
    assert any("hp-identity-fixed" in w for w in warnings), warnings
    by_name = _hp_by_name(s, hunt.id)
    assert min(h for _, h in by_name["Light"]) == 1.0
    assert min(h for _, h in by_name["Diego"]) == 0.0
    s.close()


def test_stale_silence_cannot_attract_swap():
    """Live hunt-4 shape: the labeled hunter's only in-window tick lands
    0.1s after the zero (last hit going down) and the other hunter's
    silence started 47s earlier (his own earlier faint). Nothing is
    reassigned: the zeros stay put and no identity fix is claimed."""
    s = _session()
    snaps = (_ticks("Light", [(40, 99), (150, 200)])
             + _ticks("Diego", [(40, 50), (160, 200)]))
    snaps.append({"display_name": "Light", "ts_offset_seconds": 100.1,
                  "cumulative_damage": 9999.0, "instant_dps": 10.0})
    health = (_hp("Light", [(90, 0.7), (95, 0.4), (100, 0.0), (105, 0.0),
                             (110, 1.0), (120, 1.0)])
              + _hp("Diego", [(90, 1.0), (120, 1.0), (150, 1.0)]))
    hunt, created, warnings = upsert_hunt(s, _payload(snaps, health))
    assert created is True
    assert not any("hp-identity-fixed" in w for w in warnings), warnings
    by_name = _hp_by_name(s, hunt.id)
    assert min(h for _, h in by_name["Light"]) == 0.0  # untouched
    assert min(h for _, h in by_name["Diego"]) == 1.0
    s.close()
