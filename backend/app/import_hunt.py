"""Importer: fork HuntExports JSON (PoogieQuestStatisticsModel) -> upsert_hunt payload.

Dump schema (audited 2026-09-06 against Diegoeyza/HunterPie@analytics-export):
  game_type/started_at/finished_at/uploaded_at/quest/players/monsters/hash
  players[].{name, weapon (Wilds Weapon enum id), damages[{damage, dealt_at}],
             abnormalities, is_hunterpie_user}
  monsters[].{id, variant, max_health, crown, enrage.activations[],
               ailments[{id, activations[]}],
               hunt_started_at, hunt_finished_at, hunt_type, health_steps[]}
  quest.{id, type, level, stars, deaths, max_deaths} -> hunts quest_* columns

Known gaps (logged as warnings, not silently dropped):
- multi-monster quests register one hunt per monster (quest x monster),
  each carrying the FULL quest damage (per-hit damage can't be
  attributed per monster, and a quest's damage belongs to the quest)
- monsters barely touched (environment bystanders, not quest targets)
  are skipped: HP never falls below 40%. Empty HP data is
  kept (benefit of the doubt for older dumps).
- quests where no monster's HP fell below 40% register nothing (nothing
  was really fought) — unless the quest was failed (carts), which always
  registers; failed hunts are stored with cleared=False.
- dump carries no HunterPie/game versions -> CLI flags with defaults
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import settings
from .abnormalities import AbnormalityId
from .db import init_db, make_session
from .ingest import upsert_hunt
from .models import Monster, Weapon

log = logging.getLogger(__name__)

# HunterPie.Core/Game/Enums/Weapon.cs (byte enum, 255 = None)
WEAPONS = [
    "Greatsword", "SwordAndShield", "DualBlades", "Longsword", "Hammer",
    "HuntingHorn", "Lance", "GunLance", "SwitchAxe", "ChargeBlade",
    "InsectGlaive", "Bow", "HeavyBowgun", "LightBowgun",
]

DEFAULT_HUNTERPIE_VERSION = "2.14.0.466-analytics"
DEFAULT_GAME_VERSION = "1.042.00.03"

# --- HuntExports source discovery -----------------------------------------
# Two independent sources may feed the importer (either may be absent):
#   * the HunterPie analytics-export fork  -> damage / weapons / DPS curves
#   * the REFramework HuntDumper mod       -> awards / HP curve / local weapon
# Windows paths are resolved for the packaged desktop build; the dev workflow
# runs under Linux/WSL where the same folders appear under /mnt/c.

_WSL_HUNTERPIE = Path("/mnt/c/Program Files/HunterPie/HuntExports")
_WSL_HUNTERPIE_XML = Path("/mnt/c/Program Files/HunterPie/Languages/en-us.xml")
_WSL_REF = Path(
    "/mnt/c/Program Files (x86)/Steam/steamapps/common/MonsterHunterWilds"
    "/reframework/data/HuntExports")
_WILDS_REF_REL = Path("steamapps/common/MonsterHunterWilds/reframework/data/HuntExports")
# MO2 virtualizes writes under the game dir into <instance>/overwrite.
_MO2_OVERWRITE_REL = Path("overwrite/reframework/data/HuntExports")

# Bundled Wilds names so `seeds/` import without a HunterPie install.
BUNDLED_NAMES_JSON = Path(__file__).resolve().parent / "data" / "wilds_monster_names.json"


def _dedupe(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(p).lower() if os.name == "nt" else str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _hunterpie_dir_candidates_nt(
        localappdata: str | None,
        program_files: list[str | None]) -> list[Path]:
    """Pure builder for the Windows candidates (unit-testable off-Windows)."""
    cands: list[Path] = []
    if localappdata:
        cands.append(Path(localappdata) / "HunterPie" / "HuntExports")
    for base in program_files:
        if base:
            cands.append(Path(base) / "HunterPie" / "HuntExports")
    return _dedupe(cands)


def _hunterpie_dir_candidates() -> list[Path]:
    """Possible HunterPie HuntExports folders on this machine."""
    if os.name != "nt":
        return [_WSL_HUNTERPIE]
    return _hunterpie_dir_candidates_nt(
        os.environ.get("LOCALAPPDATA"),
        [os.environ.get(v) for v in
         ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432")],
    )


def _parse_library_folders(vdf_text: str) -> list[Path]:
    """Library roots from a Steam ``libraryfolders.vdf`` body.

    VDF escapes backslashes (``D:\\Steam``), so unescape them. Pure and
    side-effect free so it can be unit-tested off-Windows.
    """
    return [Path(raw.replace("\\\\", "\\"))
            for raw in re.findall(r'"path"\s*"([^"]+)"', vdf_text)]


def _steam_install_root() -> Path | None:
    """Steam install root from HKCU\\Software\\Valve\\Steam\\SteamPath."""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            return Path(winreg.QueryValueEx(key, "SteamPath")[0])
    except Exception:
        return None


def _steam_library_roots() -> list[Path]:
    """Steam install roots: HKCU SteamPath + every library in libraryfolders.vdf."""
    if os.name != "nt":
        return []
    roots: list[Path] = []
    steam = _steam_install_root()
    if steam is not None:
        roots.append(steam)
        vdf = steam / "steamapps" / "libraryfolders.vdf"
        try:
            roots.extend(_parse_library_folders(
                vdf.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            pass
    return _dedupe(roots)


def _reframework_dirs_from_roots(roots: list[Path]) -> list[Path]:
    """Pure builder: one REFramework HuntExports path per Steam library root."""
    return _dedupe([root / _WILDS_REF_REL for root in roots])


def _mo2_overwrite_candidates() -> list[Path]:
    """Mod Organizer 2 instances' overwrite folders.

    MO2 redirects writes made under the virtual game dir into the instance's
    ``overwrite/`` folder, so REFramework dumps land there. Standard instances
    live under ``%LOCALAPPDATA%/ModOrganizer/<name>``; portable instances can
    be anywhere, hence the user-configurable folder list.
    """
    if os.name != "nt":
        return []
    bases: list[Path] = []
    for var in ("LOCALAPPDATA", "APPDATA"):
        base = os.environ.get(var)
        if base:
            bases.append(Path(base) / "ModOrganizer")
    out: list[Path] = []
    for base in _dedupe(bases):
        if not base.is_dir():
            continue
        try:
            instances = sorted(p for p in base.iterdir() if p.is_dir())
        except OSError:
            continue
        out.extend(inst / _MO2_OVERWRITE_REL for inst in instances)
    return _dedupe(out)


def _reframework_dir_candidates() -> list[Path]:
    """Possible REFramework HuntExports folders on this machine."""
    if os.name != "nt":
        return [_WSL_REF]
    return _dedupe([
        *_reframework_dirs_from_roots(_steam_library_roots()),
        *_mo2_overwrite_candidates(),
    ])


def _configured_export_dirs() -> list[Path]:
    """Extra folders added in the dashboard settings (fail-soft)."""
    try:
        return settings.configured_export_dirs()
    except Exception:  # never let a bad config break ingestion
        log.warning("could not load configured export dirs", exc_info=True)
        return []


def _bundled_fork_candidates() -> list[Path]:
    """The fork we install beside the app writes to <its own dir>\\HuntExports."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return []
    app_dir = Path(sys.executable).resolve().parent
    return [app_dir / "HunterPie-Fork" / "HuntExports"]


def _configured_kind_dirs() -> tuple[list[Path], list[Path]]:
    """Split user folders by kind for the status note (path-based heuristic)."""
    configured = _configured_export_dirs()
    ref = [p for p in configured if "reframework" in str(p).lower()]
    pie = [p for p in configured if p not in ref]
    return pie, ref


def known_export_dirs() -> list[Path]:
    """Every candidate source folder (existing or not) — for messages."""
    return _dedupe([
        *_hunterpie_dir_candidates(),
        *_bundled_fork_candidates(),
        *_reframework_dir_candidates(),
        *_configured_export_dirs(),
    ])


def detected_sources() -> list[dict[str, str]]:
    """Existing export folders tagged by kind — for the dashboard status note."""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    pie_configured, ref_configured = _configured_kind_dirs()
    groups = (
        ("hunterpie", [*_hunterpie_dir_candidates(), *_bundled_fork_candidates(),
                       *pie_configured]),
        ("reframework", [*_reframework_dir_candidates(), *ref_configured]),
    )
    for kind, candidates in groups:
        for path in candidates:
            if not path.is_dir():
                continue
            key = str(path).lower() if os.name == "nt" else str(path)
            if key in seen:
                continue
            seen.add(key)
            out.append({"kind": kind, "path": str(path)})
    return out


def default_export_dirs() -> list[Path]:
    """Candidate source folders that actually exist.

    HunterPie first so its richer dump wins ties, then REFramework.
    """
    return [p for p in known_export_dirs() if p.is_dir()]


def _names_xml_candidates() -> list[Path]:
    if os.name != "nt":
        return [_WSL_HUNTERPIE_XML]
    cands: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        cands.append(Path(local) / "HunterPie" / "Languages" / "en-us.xml")
    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        base = os.environ.get(var)
        if base:
            cands.append(Path(base) / "HunterPie" / "Languages" / "en-us.xml")
    return _dedupe(cands)


def default_names_xml() -> Path | None:
    for p in _names_xml_candidates():
        if p.exists():
            return p
    return None


def parse_ts(value: str) -> datetime:
    """Parse HunterPie timestamps: trailing Z, up to 7 fractional digits."""
    v = value.strip().replace("Z", "+00:00").replace("z", "+00:00")
    v = re.sub(r"(\.\d{6})\d+(\+|$)", r"\1\2", v)
    dt = datetime.fromisoformat(v)
    return dt.astimezone(UTC).replace(tzinfo=None)


def load_monster_names(xml_path: str | Path | None = None) -> dict[int, str]:
    """Monster names from the Wilds section only — Rise/World reuse the same
    numeric ids (e.g. 31 = Tetranadon/Paolumu/Xu Wu).

    Resolution order: explicit --names-xml > HunterPie default path >
    repo-bundled data/wilds_monster_names.json (so seeds/ work anywhere).
    """
    import xml.etree.ElementTree as ET

    if isinstance(xml_path, str):
        xml_path = Path(xml_path)
    path = xml_path or default_names_xml()
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


ENGAGEMENT_FLOOR = 0.40
"""A monster counts as fought when its HP falls below this fraction.

HP tracking can't tell player damage from monster-vs-monster damage, so a
bystander that loses a quarter of its HP to a turf war (or your splash
damage) is treated as a target. Tighten only with per-hit attribution.
"""


def _min_hp_frac(m: dict) -> float | None:
    """Lowest sampled HP fraction, or None when the monster has no HP data."""
    fracs = [s.get("percentage") for s in (m.get("health_steps") or [])
             if isinstance(s.get("percentage"), (int, float))]
    return min(fracs) if fracs else None


def _quest_failed(doc: dict) -> bool:
    """Quest outcome: explicit result first, then cart limit as a fallback.

    HunterDumper records `quest.result` (success/fail/quit) from the game's
    SuccessState. Older dumps only carry deaths, which could not express a
    time-up failure (the reward screen appears for those too).
    """
    quest = doc.get("quest") or {}
    result = quest.get("result")
    if result in ("fail", "quit"):
        return True
    if result == "success":
        return False
    if quest.get("cleared") is False:
        return True
    max_deaths = quest.get("max_deaths") or 0
    return bool(max_deaths and (quest.get("deaths") or 0) >= max_deaths)


def _is_environment_bystander(m: dict) -> bool:
    """True when the monster was barely touched: incidental environment
    damage, not a quest target. Requires positive evidence (HP samples
    never falling below 40% HP); empty HP data keeps the monster
    (benefit of the doubt for older dumps)."""
    low = _min_hp_frac(m)
    if low is None:
        return False
    return low >= ENGAGEMENT_FLOOR


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
    # Only trust weapon_name from dumps that carry the explicit mod marker
    # (`source`): older mod versions emitted swapped per-player names.
    trust_name = bool(doc.get("source"))

    monsters = doc.get("monsters") or []
    if not monsters:
        raise ValueError("dump has no monsters")
    if len(monsters) > 1:
        warnings.append(f"multi-monster quest: registering one hunt per monster "
                        f"(ids={[m['id'] for m in monsters]}), "
                        f"each with full quest damage")

    # Same hunter listed twice = disconnect/rejoin: merge damage frames so
    # each hunt keeps one row per hunter (UNIQUE hunt_id/player_id).
    merged: dict[str, dict] = {}
    for p in doc.get("players") or []:
        name = p.get("name")
        entry = merged.setdefault(name, {"weapon": p.get("weapon"),
                                         "gear": None,
                                         "is_supporter": bool(p.get("is_supporter", False)),
                                         "weapon_name": p.get("weapon_name") if trust_name else None,
                                         "awards": None, "health": None,
                                         "damages": [], "abnormalities": []})
        # Gear fingerprint (fork >= gear build, local player only):
        # first non-null snapshot wins; stats are taken at quest start.
        if entry["gear"] is None and p.get("gear"):
            entry["gear"] = p["gear"]
        # Awards/hunter highlights (REFramework mod): keep the first non-empty.
        if entry["awards"] is None and p.get("awards"):
            entry["awards"] = p["awards"]
        # Player HP samples (REFramework mod): keep the first non-empty.
        if entry["health"] is None and p.get("health_steps"):
            entry["health"] = p["health_steps"]
        if trust_name and entry["weapon_name"] is None and p.get("weapon_name"):
            entry["weapon_name"] = p["weapon_name"]
        entry["damages"].extend(p.get("damages") or [])
        entry["abnormalities"].extend(p.get("abnormalities") or [])
        entry_total = sum(f.get("damage", 0) for f in p.get("damages") or [])
        if entry_total > entry.get("_best_total", -1):
            entry["_best_total"] = entry_total
            entry["weapon"] = p.get("weapon")
    if len(merged) != len(doc.get("players") or []):
        warnings.append(f"merged {len(doc.get('players') or []) - len(merged)} duplicate "
                        f"player entr{'y' if len(doc.get('players', [])) - len(merged) == 1 else 'ies'} "
                        f"(disconnect/rejoin)")

    out = []
    failed = _quest_failed(doc)
    if failed:
        warnings.append("quest failed (carts): registering all "
                        f"{len(monsters)} monsters")
    else:
        tracked = [(m, _min_hp_frac(m)) for m in monsters]
        tracked = [(m, low) for m, low in tracked if low is not None]
        if tracked and all(low >= ENGAGEMENT_FLOOR for _, low in tracked):
            warnings.append("no monster HP fell below "
                            f"{ENGAGEMENT_FLOOR:.0%}: nothing targeted, "
                            "quest skipped")
            return []
    for m in monsters:
        if not failed and len(monsters) > 1 and _is_environment_bystander(m):
            warnings.append(f"skipping environment monster id={m['id']} "
                            f"(HP never below {ENGAGEMENT_FLOOR:.0%}, "
                            f"not a quest target)")
            continue
        out.append((_monster_payload(doc, m, merged, started, finished,
                                     names, hunterpie_version, game_version,
                                     cleared=not failed),
                    warnings))
    # Multi-monster quests carry the FULL quest damage on every sibling row;
    # flag them so stats can attribute or exclude shared damage later.
    is_split = len(out) > 1
    for payload, _ in out:
        payload["is_split_quest"] = is_split
    # Awards/hunter highlights are quest-level (not per monster): keep them on
    # the primary (first) hunt so a split quest can't double-count them across
    # sibling rows in the aggregate highlight leaderboards. Player HP is also
    # quest-wide, but it stays on EVERY sibling: the Survival tab reads one
    # hunt at a time, so duplicating it means clicking any monster of a
    # multi-monster quest still shows the party's HP.
    for payload, _ in out[1:]:
        for p in payload["players"]:
            p["awards"] = []
        payload["awards_meta"] = None
    return out


def _doc_source(doc: dict) -> str:
    """Which tool produced this dump. Our mod marks it explicitly; older mod
    dumps are detected by their awards payload. HunterPie's fork dump has
    neither, so it is the authoritative 'hunterpie' source."""
    if doc.get("source"):
        return str(doc["source"])
    marked = "awards_meta" in doc or any(
        "awards" in p for p in (doc.get("players") or []))
    return "reframework" if marked else "hunterpie"


def _monster_payload(doc: dict, m: dict, merged: dict[str, dict],
                     started: datetime, finished: datetime | None,
                     names: dict[int, str],
                     hunterpie_version: str, game_version: str,
                     cleared: bool = True) -> dict:
    players = []
    snapshots = []
    abnormalities = []
    player_health = []
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
            "is_supporter": bool(p.get("is_supporter", False)),
            "weapon_name": p.get("weapon_name"),
            "awards": p.get("awards") or [],
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
            category = AbnormalityId.parse(ab_id).group
            for act in ab.get("activations") or []:
                abnormalities.append({
                    "display_name": name,
                    "abnormality_id": ab_id,
                    "category": category,
                    "started_at_offset": (parse_ts(act["started_at"]) - started).total_seconds(),
                    "finished_at_offset": (parse_ts(act["finished_at"]) - started).total_seconds()
                    if act.get("finished_at") else None,
                })
        for h in p.get("health") or []:
            frac = h.get("percentage")
            if not h.get("time") or not isinstance(frac, (int, float)):
                continue
            red = h.get("red_percentage")
            player_health.append({
                "display_name": name,
                "ts_offset_seconds": (parse_ts(h["time"]) - started).total_seconds(),
                "hp_fraction": frac,
                "red_fraction": red if isinstance(red, (int, float)) else None,
                "max_hp": h.get("max_hp") if isinstance(h.get("max_hp"), (int, float)) else None,
            })

    events = []
    for a in (m.get("enrage") or {}).get("activations") or []:
        events.append({
            "event_type": "enrage",
            "start_offset_seconds": (parse_ts(a["started_at"]) - started).total_seconds(),
            "end_offset_seconds": (parse_ts(a["finished_at"]) - started).total_seconds()
            if a.get("finished_at") else None,
        })
    # Monster ailments (HunterPie fork >= ailment build). Several memory slots
    # map to the same status (two poison ids, two stun ids, ...), so the fork
    # normally already merged them; dedupe exact windows defensively because
    # monster_events is unique on (hunt, monster, type, start).
    seen_status: set[tuple[str, float]] = set()
    for ailment in m.get("ailments") or []:
        raw_id = str(ailment.get("id") or "")
        name = raw_id.upper().removeprefix("AILMENT_").lower()
        if not name or name in {"enrage", "unknown"}:
            continue
        for a in ailment.get("activations") or []:
            if not a.get("started_at"):
                continue
            start_s = (parse_ts(a["started_at"]) - started).total_seconds()
            event = {
                "event_type": f"ailment.{name}",
                "start_offset_seconds": start_s,
                "end_offset_seconds": (parse_ts(a["finished_at"]) - started).total_seconds()
                if a.get("finished_at") else None,
            }
            key = (event["event_type"], round(start_s, 3))
            if key in seen_status:
                continue
            seen_status.add(key)
            events.append(event)

    hp_steps = [{
        "ts_offset_seconds": (parse_ts(s["time"]) - started).total_seconds(),
        "hp_fraction": s["percentage"],
    } for s in (m.get("health_steps") or []) if s.get("time")]

    quest = doc.get("quest") or {}
    # stars=0 means "unknown" from the fork (no 0-star quests exist).
    quest_stars = quest.get("stars") or None
    return {
        "quest_id_external": doc.get("hash"),
        "monster_id": m["id"],
        "_monster_name": names.get(m["id"], f"Monster_{m['id']}"),
        "quest_id": quest.get("id"),
        "quest_type": quest.get("type"),
        "quest_level": quest.get("level"),
        "quest_stars": quest_stars,
        "monster_max_hp": m.get("max_health"),
        "monster_variant": m.get("variant"),
        "monster_crown": m.get("crown"),
        "started_at": started,
        "ended_at": finished,
        "quest_time_seconds": (finished - started).total_seconds() if finished else None,
        "real_hunt_time_seconds": None,
        "cart_count": quest.get("deaths") or 0,
        "cleared": cleared,
        "players": players,
        "snapshots": snapshots,
        "abnormalities": abnormalities,
        "player_health": player_health,
        "events": events,
        "hp_steps": hp_steps,
        "awards_meta": doc.get("awards_meta"),
        "source": _doc_source(doc),
        "hunterpie_version": hunterpie_version,
        "game_version": game_version,
        "mod_version": doc.get("mod_version"),
    }


def import_doc(session, doc: dict, names: dict[int, str],
               hunterpie_version: str, game_version: str,
               cache: dict | None = None):
    results = []
    for payload, warnings in poogie_to_payloads(doc, names, hunterpie_version,
                                                game_version):
        # Always go through upsert_hunt: it owns dedup AND the cross-source
        # rules (a later HunterPie dump refreshes a mod-created hunt, the mod
        # only contributes awards). An early skip here would bypass those.
        ensure_monster(session, payload["monster_id"], names)
        for p in payload["players"]:
            p["weapon_id"] = ensure_weapon(session, p.pop("_weapon_enum"))
        session.commit()  # persist reference rows before the hunt transaction
        hunt, created, upsert_warnings = upsert_hunt(session, payload,
                                                     cache=cache)
        results.append((hunt, created, warnings + upsert_warnings))
    return results


def import_file(db_path: str, file_path: str, hunterpie_version: str,
                game_version: str, names_xml: str | None) -> None:
    names = load_monster_names(Path(names_xml) if names_xml else None)
    doc = json.loads(Path(file_path).read_text(encoding="utf-8-sig"))
    init_db(db_path)
    session = make_session(db_path)
    results = import_doc(session, doc, names, hunterpie_version, game_version)
    if not results:
        log.info("skipped %s: no targeted monsters (no HP below %.0f%%)",
                 file_path, ENGAGEMENT_FLOOR * 100)
        return
    for hunt, created, warnings in results:
        log.info("%s hunt id=%s from %s",
                 'imported' if created else 'duplicate-skipped', hunt.id,
                 file_path)
        for w in warnings:
            log.warning("hunt id=%s: %s", hunt.id, w)


def main() -> None:
    ap = argparse.ArgumentParser(description="Import fork HuntExports JSON into hunts.db")
    ap.add_argument("--db", required=True)
    src = ap.add_mutually_exclusive_group(required=False)
    src.add_argument("--file")
    src.add_argument("--dir", action="append",
                     help="import all *.json from this dir (repeatable; "
                          "re-imports dedup safely)")
    ap.add_argument("--hunterpie-version", default=DEFAULT_HUNTERPIE_VERSION)
    ap.add_argument("--game-version", default=DEFAULT_GAME_VERSION)
    ap.add_argument("--names-xml", default=None)
    args = ap.parse_args()

    if args.file:
        import_file(args.db, args.file, args.hunterpie_version,
                    args.game_version, args.names_xml)
        return

    # No --dir: scan every known source that exists (either may be absent).
    dirs = args.dir or [str(d) for d in default_export_dirs()]
    if not dirs:
        looked = "\n".join(f"  {d}" for d in known_export_dirs())
        print("no export dirs found (looked in:\n" + looked + ")")
        return
    print("Importing from: " + ", ".join(dirs))
    from .import_job import run_import

    def _show(snap: dict) -> None:
        print(f"\r  {snap['scanned']}/{snap['total']} files "
              f"({snap['imported']} new, {snap['duplicates']} dupes, "
              f"{snap['skipped_manifest']} skipped)", end="", flush=True)

    result = run_import(args.db, dirs, progress=_show)
    print()
    print(f"scanned={result['scanned']} imported={result['imported']} "
          f"duplicates={result['duplicates']} "
          f"skipped={result['skipped_manifest']} "
          f"errors={len(result['errors'])}")
    for e in result["errors"]:
        print(f"  FAILED {e['file']}: {e['error']}")


if __name__ == "__main__":
    main()
