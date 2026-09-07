"""Importer: fork HuntExports JSON (PoogieQuestStatisticsModel) -> upsert_hunt payload.

Dump schema (audited 2026-09-06 against Diegoeyza/HunterPie@analytics-export):
  game_type/started_at/finished_at/uploaded_at/quest/players/monsters/hash
  players[].{name, weapon (Wilds Weapon enum id), damages[{damage, dealt_at}],
             abnormalities, is_hunterpie_user}
  monsters[].{id, variant, max_health, crown, enrage.activations[],
               hunt_started_at, hunt_finished_at, hunt_type, health_steps[]}
  quest.{id, type, level, stars, deaths, max_deaths} -> hunts quest_* columns

Known gaps (logged as warnings, not silently dropped):
- player abnormalities have no table yet (count reported)
- multi-monster quests register one hunt per monster (quest x monster),
  each carrying the FULL quest damage (per-hit damage can't be
  attributed per monster, and a quest's damage belongs to the quest)
- dump carries no HunterPie/game versions -> CLI flags with defaults
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .db import init_db, make_session
from .ingest import upsert_hunt
from .models import Monster, Weapon

# HunterPie.Core/Game/Enums/Weapon.cs (byte enum, 255 = None)
WEAPONS = [
    "Greatsword", "SwordAndShield", "DualBlades", "Longsword", "Hammer",
    "HuntingHorn", "Lance", "GunLance", "SwitchAxe", "ChargeBlade",
    "InsectGlaive", "Bow", "HeavyBowgun", "LightBowgun",
]

DEFAULT_HUNTERPIE_VERSION = "2.14.0.466-analytics"
DEFAULT_GAME_VERSION = "1.042.00.02"
DEFAULT_NAMES_XML = Path("/mnt/c/Program Files/HunterPie/Languages/en-us.xml")
# Bundled Wilds names so `seeds/` import without a HunterPie install.
BUNDLED_NAMES_JSON = Path(__file__).resolve().parent / "data" / "wilds_monster_names.json"


def parse_ts(value: str) -> datetime:
    """Parse HunterPie timestamps: trailing Z, up to 7 fractional digits."""
    v = value.strip().replace("Z", "+00:00").replace("z", "+00:00")
    v = re.sub(r"(\.\d{6})\d+(\+|$)", r"\1\2", v)
    dt = datetime.fromisoformat(v)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def load_monster_names(xml_path: str | Path | None = None) -> dict[int, str]:
    """Monster names from the Wilds section only — Rise/World reuse the same
    numeric ids (e.g. 31 = Tetranadon/Paolumu/Xu Wu).

    Resolution order: explicit --names-xml > HunterPie default path >
    repo-bundled data/wilds_monster_names.json (so seeds/ work anywhere).
    """
    import xml.etree.ElementTree as ET

    if isinstance(xml_path, str):
        xml_path = Path(xml_path)
    path = xml_path or (DEFAULT_NAMES_XML if DEFAULT_NAMES_XML.exists() else None)
    if path is not None and path.exists():
        root = ET.parse(str(path)).getroot()
        wilds = root.find("./Monsters/Wilds")
        if wilds is None:
            return {}
        return {int(m.get("Id")): m.get("String", "")
                for m in wilds.iter("Monster") if m.get("Id")}
    if BUNDLED_NAMES_JSON.exists():
        return {int(k): v for k, v in
                json.loads(BUNDLED_NAMES_JSON.read_text(encoding="utf-8")).items()}
    return {}


def ensure_weapon(session, weapon_id: int | None) -> int | None:
    if weapon_id is None or weapon_id == 255 or weapon_id >= len(WEAPONS):
        return None
    name = WEAPONS[weapon_id]
    row = session.get(Weapon, weapon_id + 1)
    if row is None:
        row = Weapon(id=weapon_id + 1, name=name, weapon_type=name)
        session.add(row)
        session.flush()
    return row.id


def ensure_monster(session, monster_id: int, names: dict[int, str]) -> int:
    row = session.get(Monster, monster_id)
    if row is None:
        row = Monster(id=monster_id,
                      name=names.get(monster_id, f"Monster_{monster_id}"))
        session.add(row)
        session.flush()
    else:
        resolved = names.get(monster_id)
        if resolved and row.name != resolved:
            row.name = resolved
    return row.id


def poogie_to_payloads(doc: dict, names: dict[int, str],
                        hunterpie_version: str, game_version: str
                        ) -> list[tuple[dict, list[str]]]:
    """One payload per monster (quest x monster combinations all register).

    Each hunt carries the FULL quest damage: per-hit damage can't be
    attributed per monster, and a quest's damage belongs to the quest.
    Single-monster quests are unaffected.
    """
    warnings: list[str] = []
    started = parse_ts(doc["started_at"])
    finished = parse_ts(doc["finished_at"]) if doc.get("finished_at") else None

    monsters = doc.get("monsters", [])
    if not monsters:
        raise ValueError("dump has no monsters")
    if len(monsters) > 1:
        warnings.append(f"multi-monster quest: registering one hunt per monster "
                        f"(ids={[m['id'] for m in monsters]}), "
                        f"each with full quest damage")

    # Same hunter listed twice = disconnect/rejoin: merge damage frames so
    # each hunt keeps one row per hunter (UNIQUE hunt_id/player_id).
    merged: dict[str, dict] = {}
    for p in doc.get("players", []):
        name = p.get("name")
        entry = merged.setdefault(name, {"weapon": p.get("weapon"),
                                         "gear": None,
                                         "damages": [], "abnormalities": []})
        # Gear fingerprint (fork >= gear build, local player only):
        # first non-null snapshot wins; stats are taken at quest start.
        if entry["gear"] is None and p.get("gear"):
            entry["gear"] = p["gear"]
        entry["damages"].extend(p.get("damages", []))
        entry["abnormalities"].extend(p.get("abnormalities", []))
        entry_total = sum(f.get("damage", 0) for f in p.get("damages", []))
        if entry_total > entry.get("_best_total", -1):
            entry["_best_total"] = entry_total
            entry["weapon"] = p.get("weapon")
    if len(merged) != len(doc.get("players", [])):
        warnings.append(f"merged {len(doc.get('players', [])) - len(merged)} duplicate "
                        f"player entr{'y' if len(doc.get('players', [])) - len(merged) == 1 else 'ies'} "
                        f"(disconnect/rejoin)")

    out = []
    for m in monsters:
        out.append((_monster_payload(doc, m, merged, started, finished,
                                     names, hunterpie_version, game_version),
                    warnings))
    return out


def _monster_payload(doc: dict, m: dict, merged: dict[str, dict],
                     started: datetime, finished: datetime | None,
                     names: dict[int, str],
                     hunterpie_version: str, game_version: str) -> dict:
    players = []
    snapshots = []
    abnormalities = []
    for name, p in merged.items():
        frames = sorted(p["damages"], key=lambda f: f["dealt_at"])
        total = sum(f.get("damage", 0) for f in frames)
        peak = max((f.get("damage", 0) for f in frames), default=0)
        players.append({
            "display_name": name,
            "_weapon_enum": p.get("weapon"),
            "gear": p.get("gear"),
            "total_damage": total,
            "peak_dps": peak,  # ~1s sampling: max single-frame damage
            "is_supporter": False,  # dump has no supporter flag; revisit if seen
        })
        cum, prev = 0.0, None
        for f in frames:
            ts = parse_ts(f["dealt_at"])
            dmg = f.get("damage", 0)
            cum += dmg
            dt = (ts - prev).total_seconds() if prev else 1.0
            snapshots.append({
                "display_name": name,
                "ts_offset_seconds": (ts - started).total_seconds(),
                # dealt_at past finished_at is a tail flush: tolerate, don't filter
                "cumulative_damage": cum,
                "instant_dps": dmg / dt if dt > 0 else 0.0,
            })
            prev = ts
        for ab in p["abnormalities"]:
            ab_id = ab["id"]
            category = ab_id.split("_")[0] if "_" in ab_id else "Unknown"
            for act in ab.get("activations", []):
                abnormalities.append({
                    "display_name": name,
                    "abnormality_id": ab_id,
                    "category": category,
                    "started_at_offset": (parse_ts(act["started_at"]) - started).total_seconds(),
                    "finished_at_offset": (parse_ts(act["finished_at"]) - started).total_seconds()
                    if act.get("finished_at") else None,
                })

    events = []
    for a in (m.get("enrage") or {}).get("activations", []):
        events.append({
            "event_type": "enrage",
            "start_offset_seconds": (parse_ts(a["started_at"]) - started).total_seconds(),
            "end_offset_seconds": (parse_ts(a["finished_at"]) - started).total_seconds()
            if a.get("finished_at") else None,
        })

    hp_steps = [{
        "ts_offset_seconds": (parse_ts(s["time"]) - started).total_seconds(),
        "hp_fraction": s["percentage"],
    } for s in (m.get("health_steps") or []) if s.get("time")]

    quest = doc.get("quest") or {}
    return {
        "quest_id_external": doc.get("hash"),
        "monster_id": m["id"],
        "_monster_name": names.get(m["id"], f"Monster_{m['id']}"),
        "quest_id": quest.get("id"),
        "quest_type": quest.get("type"),
        "quest_level": quest.get("level"),
        "quest_stars": quest.get("stars"),
        "monster_max_hp": m.get("max_health"),
        "monster_variant": m.get("variant"),
        "monster_crown": m.get("crown"),
        "started_at": started,
        "ended_at": finished,
        "quest_time_seconds": (finished - started).total_seconds() if finished else None,
        "real_hunt_time_seconds": None,
        "cart_count": quest.get("deaths") or 0,
        "cleared": True,  # dump only written on QuestStatus.Success
        "players": players,
        "snapshots": snapshots,
        "abnormalities": abnormalities,
        "events": events,
        "hp_steps": hp_steps,
        "hunterpie_version": hunterpie_version,
        "game_version": game_version,
    }


def import_doc(session, doc: dict, names: dict[int, str],
               hunterpie_version: str, game_version: str):
    results = []
    for payload, warnings in poogie_to_payloads(doc, names, hunterpie_version,
                                                game_version):
        ensure_monster(session, payload["monster_id"], names)
        for p in payload["players"]:
            p["weapon_id"] = ensure_weapon(session, p.pop("_weapon_enum"))
        session.commit()  # persist reference rows before the hunt transaction
        hunt, created, upsert_warnings = upsert_hunt(session, payload)
        results.append((hunt, created, warnings + upsert_warnings))
    return results


def import_file(db_path: str, file_path: str, hunterpie_version: str,
                game_version: str, names_xml: str | None) -> None:
    names = load_monster_names(Path(names_xml) if names_xml else None)
    doc = json.loads(Path(file_path).read_text(encoding="utf-8-sig"))
    init_db(db_path)
    session = make_session(db_path)
    for hunt, created, warnings in import_doc(
            session, doc, names, hunterpie_version, game_version):
        print(f"{'imported' if created else 'duplicate-skipped'} hunt id={hunt.id} "
              f"from {file_path}")
        for w in warnings:
            print(f"  warning: {w}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Import fork HuntExports JSON into hunts.db")
    ap.add_argument("--db", required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file")
    src.add_argument("--dir", help="import all *.json (re-imports dedup safely)")
    ap.add_argument("--hunterpie-version", default=DEFAULT_HUNTERPIE_VERSION)
    ap.add_argument("--game-version", default=DEFAULT_GAME_VERSION)
    ap.add_argument("--names-xml", default=None)
    args = ap.parse_args()

    files = [args.file] if args.file else sorted(str(p) for p in Path(args.dir).glob("*.json"))
    if not files:
        raise SystemExit(f"no *.json in {args.dir}")
    for f in files:
        import_file(args.db, f, args.hunterpie_version, args.game_version, args.names_xml)


if __name__ == "__main__":
    main()
