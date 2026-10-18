"""Runtime path helpers + export-source detection (packaged-build support)."""
import sys
from pathlib import Path

import pytest

from app import import_hunt, paths


def test_resource_path_source_root():
    # Unfrozen, resource_path is anchored at the repo root.
    root = Path(paths.__file__).resolve().parent.parent.parent
    assert paths.resource_path("dashboard", "out") == root / "dashboard" / "out"


def test_user_data_dir_honors_xdg(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.os, "name", "posix")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    out = paths.user_data_dir()
    assert out == tmp_path / paths.APP_NAME
    assert out.is_dir()


def test_is_frozen_reflects_sys(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert paths.is_frozen() is False
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert paths.is_frozen() is True


def test_dedupe_case_insensitive_on_windows(monkeypatch):
    from types import SimpleNamespace

    # Patch only the module's view of os.name (never the real os module — that
    # would make pathlib build WindowsPath and explode off-Windows).
    a, b, d = Path("C:/X/HuntExports"), Path("c:/x/huntexports"), Path("D:/Y")
    monkeypatch.setattr(import_hunt, "os", SimpleNamespace(name="nt"))
    assert import_hunt._dedupe([a, b, d]) == [a, d]


def _patch_candidates(monkeypatch, hp, rf, fork=()):
    monkeypatch.setattr(import_hunt, "_hunterpie_dir_candidates", lambda: list(hp))
    monkeypatch.setattr(import_hunt, "_reframework_dir_candidates", lambda: list(rf))
    monkeypatch.setattr(import_hunt, "_bundled_fork_candidates", lambda: list(fork))


def test_detected_sources_tags_kinds(monkeypatch, tmp_path):
    hp = tmp_path / "hp"
    rf = tmp_path / "rf"
    missing = tmp_path / "nope"
    hp.mkdir()
    rf.mkdir()
    _patch_candidates(monkeypatch, [hp, missing], [rf])
    sources = import_hunt.detected_sources()
    assert {"kind": "hunterpie", "path": str(hp)} in sources
    assert {"kind": "reframework", "path": str(rf)} in sources
    assert all(missing.name not in s["path"] for s in sources)


def test_detected_sources_counts_bundled_fork_as_hunterpie(monkeypatch, tmp_path):
    fork = tmp_path / "HunterPie-Fork" / "HuntExports"
    fork.mkdir(parents=True)
    _patch_candidates(monkeypatch, [], [], [fork])
    assert import_hunt.detected_sources() == [
        {"kind": "hunterpie", "path": str(fork)}
    ]


def test_parse_library_folders_unescapes(monkeypatch):
    vdf = r'''
    "libraryfolders"
    {
        "0" { "path" "C:\\Program Files (x86)\\Steam" }
        "1" { "path" "D:\\SteamLibrary" }
    }
    '''
    assert import_hunt._parse_library_folders(vdf) == [
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"D:\SteamLibrary"),
    ]


def test_hunterpie_candidates_windows():
    local = "C:/Users/g/Local"
    pf = "C:/Program Files"
    out = import_hunt._hunterpie_dir_candidates_nt(local, [pf, None])
    assert out == [
        Path(local) / "HunterPie" / "HuntExports",
        Path(pf) / "HunterPie" / "HuntExports",
    ]


def test_reframework_dirs_from_roots(tmp_path):
    roots = [tmp_path / "steam", tmp_path / "lib2"]
    assert import_hunt._reframework_dirs_from_roots(roots) == [
        r / import_hunt._WILDS_REF_REL for r in roots
    ]


def test_default_export_dirs_only_existing(monkeypatch, tmp_path):
    existing = tmp_path / "exists"
    existing.mkdir()
    _patch_candidates(monkeypatch, [existing, tmp_path / "absent"], [])
    assert import_hunt.default_export_dirs() == [existing]


@pytest.mark.parametrize("kind", ["hunterpie", "reframework"])
def test_known_export_dirs_are_paths(monkeypatch, tmp_path, kind):
    d = tmp_path / kind
    _patch_candidates(monkeypatch, [d] if kind == "hunterpie" else [],
                      [d] if kind == "reframework" else [])
    assert d in import_hunt.known_export_dirs()
