#!/usr/bin/env python3
"""Generate the Japanese data-name tables used by the dashboard.

The dashboard resolves captured names by ID: monsters by game ID, skills /
consumables / debuffs by HunterPie short id ("Skills.159-1"). This script
produces ``dashboard/locales/ja/data.json`` so a Japanese UI shows the game's
own terminology instead of machine-translated labels.

Join rules (all vocabulary is borrowed from HunterPie, MIT licensed):

* monsters -- read ``<Monsters><Wilds><Monster Id String>>`` from
  ``ja-jp.xml``. Every ID in ``backend/app/data/wilds_monster_names.json``
  must exist, and the English entry at the same ID in ``en-us.xml`` must match
  that JSON name; a mismatch means the ID namespace drifted, so it is fatal.
* abnormalities -- for each ``<Abnormality Id Name>`` in
  ``Game/Wilds/Data/AbnormalityData.xml``, look ``Name`` up in ``ja-jp.xml``
  ``<Abnormalities>``. When ``Name`` is missing or untranslated, fall back to
  the English display name from ``backend/app/abnormalities.py``, find the
  ``en-us.xml`` entry with that ``String``, and reuse its id in ``ja-jp.xml``.
  At least 95% of ``ABNORMALITY_NAMES`` must resolve.
* awards -- hand-maintained; copied verbatim from the existing output file.

Only the standard library is used. Pinned upstream vocabulary:
    HunterPie (https://github.com/HunterPie/HunterPie), MIT License,
    commit PINNED_COMMIT.

Usage:
    python scripts/gen_names_ja.py [--hunterpie ../HunterPie] [--out PATH]
    python scripts/gen_names_ja.py --check
    python scripts/gen_names_ja.py --print-unmapped
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

#: HunterPie commit whose localization and catalog this script was pinned to.
PINNED_COMMIT = "92d3c6102d4edf3ff0334f4d5ae5a5cc18d82937"

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HUNTERPIE = REPO_ROOT.parent / "HunterPie"
DEFAULT_OUT = REPO_ROOT / "dashboard" / "locales" / "ja" / "data.json"
MONSTER_NAMES_PATH = REPO_ROOT / "backend" / "app" / "data" / "wilds_monster_names.json"

MIN_ABNORMALITY_COVERAGE = 0.95


def _load_names() -> tuple[dict[str, str], dict[str, str]]:
    """Return (monster names by id, ABNORMALITY_NAMES) from the backend data."""
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from app.abnormalities import ABNORMALITY_NAMES

    monsters = json.loads(MONSTER_NAMES_PATH.read_text(encoding="utf-8"))
    return monsters, dict(ABNORMALITY_NAMES)


def _read_xml(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


def _monster_table(root: ET.Element) -> dict[str, str]:
    section = root.find("Monsters/Wilds")
    if section is None:
        return {}
    return {
        node.get("Id", ""): (node.get("String") or "").strip()
        for node in section.findall("Monster")
    }


def _abnormality_table(root: ET.Element) -> dict[str, str]:
    section = root.find("Abnormalities")
    if section is None:
        return {}
    return {
        node.get("Id", ""): (node.get("String") or "").strip()
        for node in section.findall("Abnormality")
    }


def _catalog(path: Path) -> list[tuple[str, str | None]]:
    """HunterPie Wilds catalog entries as (short id, localization name key)."""
    return [
        (node.get("Id", ""), node.get("Name"))
        for group in _read_xml(path)
        for node in group.findall("Abnormality")
    ]


def _localized_root(hunterpie: Path, locale: str) -> ET.Element:
    return _read_xml(hunterpie / "Localization" / "localization" / f"{locale}.xml")


def _commit(hunterpie: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(hunterpie), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def build(
    hunterpie: Path, existing: dict | None
) -> tuple[dict, dict, list[tuple[str, str, str]]]:
    """Return (document, stats, unmapped); unmapped rows are (id, name, reason)."""
    monster_names, abnormality_names = _load_names()
    ja = _localized_root(hunterpie, "ja-jp")
    en = _localized_root(hunterpie, "en-us")

    ja_monsters = _monster_table(ja)
    en_monsters = _monster_table(en)
    ja_abnormalities = _abnormality_table(ja)
    en_abnormalities = _abnormality_table(en)

    monsters: dict[str, str] = {}
    drift: list[str] = []
    for monster_id, expected_en in monster_names.items():
        ja_name = ja_monsters.get(monster_id)
        if not ja_name:
            raise SystemExit(f"missing ja-jp monster for id {monster_id}")
        actual_en = en_monsters.get(monster_id)
        if actual_en != expected_en:
            drift.append(f"id {monster_id}: JSON {expected_en!r} != en-us {actual_en!r}")
            continue
        monsters[monster_id] = ja_name
    if drift:
        raise SystemExit(
            "monster ID namespace drifted; refusing to write a bad mapping:\n  "
            + "\n  ".join(drift)
        )

    # English display name -> every en-us abnormality id carrying that string.
    by_english: dict[str, list[str]] = defaultdict(list)
    for key, value in en_abnormalities.items():
        if value:
            by_english[value].append(key)

    abnormalities: dict[str, str] = {}
    unmapped: list[tuple[str, str, str]] = []
    for short_id, name in _catalog(
        hunterpie / "HunterPie" / "Game" / "Wilds" / "Data" / "AbnormalityData.xml"
    ):
        ja_name = ja_abnormalities.get(name) if name else None
        if not ja_name:
            english = abnormality_names.get(short_id)
            if not english:
                unmapped.append((short_id, name or "", "no Name and not in ABNORMALITY_NAMES"))
                continue
            candidates = by_english.get(english, [])
            if len(candidates) != 1:
                reason = (
                    f"English {english!r} matches {len(candidates)} en-us ids"
                    if candidates else f"English {english!r} absent from en-us"
                )
                unmapped.append((short_id, name or "", reason))
                continue
            ja_name = ja_abnormalities.get(candidates[0])
            if not ja_name:
                unmapped.append(
                    (short_id, candidates[0], "fallback id missing from ja-jp")
                )
                continue
        abnormalities[short_id] = ja_name

    mapped = sum(1 for key in abnormality_names if key in abnormalities)
    total = len(abnormality_names)
    coverage = mapped / total if total else 1.0
    if coverage < MIN_ABNORMALITY_COVERAGE:
        raise SystemExit(
            f"abnormality coverage {mapped}/{total} ({coverage:.1%}) is below "
            f"the {MIN_ABNORMALITY_COVERAGE:.0%} floor"
        )

    awards = dict((existing or {}).get("awards") or {})
    document = {
        "monsters": dict(sorted(monsters.items())),
        "abnormalities": dict(sorted(abnormalities.items())),
        "awards": dict(sorted(awards.items())),
    }
    stats = {
        "monsters": len(monsters),
        "abnormalities": len(abnormalities),
        "abnormality_coverage": f"{mapped}/{total}",
        "awards": len(awards),
    }
    return document, stats, unmapped


def render(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _diff(old_text: str, new_text: str) -> list[str]:
    try:
        old = json.loads(old_text)
    except json.JSONDecodeError:
        return ["existing file is not valid JSON"]
    new = json.loads(new_text)
    summary: list[str] = []
    for section in ("monsters", "abnormalities", "awards"):
        before, after = old.get(section, {}), new.get(section, {})
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
        if added or removed or changed:
            summary.append(
                f"{section}: +{len(added)} -{len(removed)} ~{len(changed)}"
            )
            for label, keys in (("+", added), ("-", removed), ("~", changed)):
                if keys:
                    sample = ", ".join(keys[:5])
                    summary.append(f"  {label} {sample}" + (" ..." if len(keys) > 5 else ""))
    return summary or ["no key-level differences"]


def _report(unmapped: list[tuple[str, str, str]]) -> None:
    if not unmapped:
        print("unmapped abnormalities: none")
        return
    print(f"unmapped abnormalities: {len(unmapped)}", file=sys.stderr)
    for short_id, name, reason in unmapped:
        print(f"  {short_id} ({name or '-'}): {reason}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hunterpie", default=str(DEFAULT_HUNTERPIE),
                        help="HunterPie checkout (default: ../HunterPie next to the repo)")
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help="output JSON path (default: dashboard/locales/ja/data.json)")
    parser.add_argument("--check", action="store_true",
                        help="verify the checked-in file is current; exit 1 if stale")
    parser.add_argument("--print-unmapped", action="store_true",
                        help="list abnormality ids that could not be mapped")
    args = parser.parse_args(argv)

    hunterpie = Path(args.hunterpie).expanduser()
    if not hunterpie.is_absolute():
        hunterpie = (REPO_ROOT / hunterpie).resolve()
    out = Path(args.out).expanduser().resolve()

    existing = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    document, stats, unmapped = build(hunterpie, existing)
    text = render(document)

    commit = _commit(hunterpie)
    if commit != PINNED_COMMIT:
        print(
            f"warning: HunterPie is at {commit or 'unknown'}, pinned {PINNED_COMMIT}",
            file=sys.stderr,
        )

    if args.print_unmapped:
        _report(unmapped)

    if args.check:
        current = out.read_text(encoding="utf-8") if out.exists() else ""
        if current == text:
            print(
                f"up to date: {stats['monsters']} monsters, "
                f"{stats['abnormalities']} abnormalities "
                f"({stats['abnormality_coverage']}), {stats['awards']} awards"
            )
            return 0
        print(f"stale: {out}", file=sys.stderr)
        for line in _diff(current, text):
            print(line, file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out} from {commit or 'unknown commit'}")
    print(
        f"  monsters: {stats['monsters']}, abnormalities: {stats['abnormalities']} "
        f"({stats['abnormality_coverage']}), awards: {stats['awards']}"
    )
    if not args.print_unmapped:
        print(f"unmapped abnormalities: {len(unmapped)} (see --print-unmapped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
