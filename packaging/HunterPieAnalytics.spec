# PyInstaller spec — onedir desktop build of HunterPie Analytics.
#
# onedir (not onefile) + no UPX: onefile unpacks a stub into %TEMP% at launch
# (a pattern malware also uses) and can't carry signatures on the DLLs it
# extracts. Every binary in an onedir build can be signed.
#
# Build (Windows, repo root):
#   set NEXT_OUTPUT=export && npm run build --prefix dashboard
#   pyinstaller --noconfirm --clean packaging/HunterPieAnalytics.spec
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent  # packaging/ -> repo root

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("app")
    + collect_submodules("webview")
    + ["sqlalchemy.dialects.sqlite"]
)

datas = [
    (str(ROOT / "dashboard" / "out"), "dashboard/out"),
    (str(ROOT / "backend" / "app" / "data"), "app/data"),
    (str(ROOT / "reframework" / "hunt_dumper.lua"), "reframework"),
]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "backend"), str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=["tkinter", "matplotlib", "numpy", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HunterPieAnalytics",
    console=False,
    disable_windowed_traceback=False,
    version=str(ROOT / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="HunterPieAnalytics",
)
