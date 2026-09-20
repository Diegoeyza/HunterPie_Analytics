"""Seed script with fake hunt data so Phases 2-3 aren't blocked on live gameplay.

Usage: python -m app.seed --db hunts.db --hunts 20

Weapon ids/names mirror import_hunt.WEAPONS (enum id + 1) so seeded rows
join variant/leaderboard logic exactly like real imports. Some hunts
carry gear fingerprints, one is SOS-flagged, one is ignored, and some
carry abnormality activations, so edge-case UI has data to render.
"""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta

from sqlalchemy import func, select

from .db import init_db, make_session
from .import_hunt import WEAPONS as IMPORTER_WEAPONS
from .ingest import upsert_hunt
from .models import Monster, Weapon

MONSTERS = [("Rathalos", "Flying Wyvern"), ("Nergigante", "Elder Dragon"), ("Zinogre", "Fanged Wyvern")]
PLAYERS = ["Diego", "Haato", "TeammateA", "TeammateB"]

GEARS = [
    {"raw": 280.0, "element": 0.0, "affinity": 15.0},
    {"raw": 310.0, "element": 120.0, "affinity": -10.0},
]


def ensure_reference_data(session) -> None:
    if session.execute(select(func.count(Monster.id))).scalar_one() == 0:
        session.add_all([Monster(name=n, species=s) for n, s in MONSTERS])
    if session.execute(select(func.count(Weapon.id))).scalar_one() == 0:
        session.add_all([Weapon(id=i + 1, name=n, weapon_type=n)
                         for i, n in enumerate(IMPORTER_WEAPONS)])
    session.commit()


def fake_hunt(i: int, rng: random.Random, max_party: int = 4) -> dict:
    monster_id = rng.randint(1, len(MONSTERS))
    # same monster, different quests: distinct ids + HP pools per monster.
    # Stars are fixed per quest id (a real quest doesn't change ★ rating).
    suffix = rng.randint(1, 2)
    quest_id = monster_id * 100 + suffix
    stars = 3 + monster_id + suffix  # 101->5★, 102->6★, ..., 302->8★
    max_hp = round(rng.uniform(12000, 16000) * (1 + stars * 0.06))
    members = rng.sample(PLAYERS, rng.randint(1, min(max_party, len(PLAYERS))))
    start = datetime(2026, 1, 1) + timedelta(days=i, hours=rng.randint(0, 20))
    quest_time = rng.uniform(300, 1500)
    # one total per member, shared by the summary row AND the curve points,
    # so curves always reconcile to totals (as the real importer guarantees)
    totals = {name: rng.uniform(2000, 20000) for name in members}
    snapshots = []
    for name in members:
        total = totals[name]
        steps = 10
        for k in range(1, steps + 1):
            snapshots.append(
                {
                    "display_name": name,
                    "ts_offset_seconds": quest_time * k / steps,
                    "cumulative_damage": total * k / steps,
                    "instant_dps": total / quest_time + rng.uniform(-5, 5),
                }
            )
    players = []
    abnormalities = []
    for n in members:
        entry: dict = {
            "display_name": n,
            "weapon_id": rng.randint(1, len(IMPORTER_WEAPONS)),
            "total_damage": totals[n],
            # biggest single ~1s frame, same scale as the real importer
            "peak_dps": totals[n] / 10 * rng.uniform(0.9, 1.8),
        }
        # Local-player gear on ~40% of hunts (variant UI needs data).
        if n == members[0] and rng.random() < 0.4:
            entry["gear"] = dict(rng.choice(GEARS))
        players.append(entry)
        if rng.random() < 0.3:
            abnormalities.append({
                "display_name": n,
                "abnormality_id": "SKILL_INSPIRATION_1",
                "category": "SKILL",
                "started_at_offset": quest_time * 0.2,
                "finished_at_offset": quest_time * 0.5,
            })
    return {
        "quest_id_external": f"seed-quest-{i:04d}",
        "monster_id": monster_id,
        "quest_id": quest_id,
        "quest_type": 0,
        "quest_level": rng.randint(1, 3),
        "quest_stars": stars,
        "monster_max_hp": max_hp,
        "monster_variant": 0,
        "monster_crown": rng.choice([0, 0, 0, 1, 2, 3]),
        "started_at": start,
        "ended_at": start + timedelta(seconds=quest_time),
        "quest_time_seconds": quest_time,
        "real_hunt_time_seconds": quest_time - rng.uniform(0, 60),
        "cart_count": rng.randint(0, 2),
        "cleared": rng.random() > 0.15,
        # Edge cases sprinkled deterministically: SOS + ignored rows.
        "is_sos": (i % 11 == 10),
        "players": players,
        "snapshots": snapshots,
        "abnormalities": abnormalities,
        "events": [{"event_type": "enrage", "start_offset_seconds": quest_time * 0.4,
                    "end_offset_seconds": quest_time * 0.55}],
        "hp_steps": [
            {"ts_offset_seconds": quest_time * k / 12,
             "hp_fraction": min(1.0, max(0.02, 1.0 - k / 12 + rng.uniform(-0.03, 0.03)))}
            for k in range(13)
        ],
        "hunterpie_version": "2.14.0",
        "game_version": "1.40.0.0",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="hunts.db")
    ap.add_argument("--hunts", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-party", type=int, default=4,
                    help="max hunters per fake hunt (Wilds parties are n-sized)")
    args = ap.parse_args()

    init_db(args.db)
    session = make_session(args.db)
    ensure_reference_data(session)
    rng = random.Random(args.seed)
    created = 0
    for i in range(args.hunts):
        hunt, was_created, _ = upsert_hunt(session, fake_hunt(i, rng, args.max_party))
        created += was_created
        # Every 13th hunt is user-hidden (ignored-filter UI needs data).
        if was_created and i % 13 == 12:
            hunt.ignored = True
            session.commit()
    print(f"seeded {created} new hunts into {args.db}")


if __name__ == "__main__":
    main()
