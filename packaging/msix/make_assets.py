"""Generate placeholder MSIX tile/splash PNGs (no third-party deps).

These are solid-colour placeholders so a package can be built in CI. Replace
them with real brand art before a public Store submission:

    python packaging/msix/make_assets.py
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "Assets"

# Brand amber (matches the dashboard palette).
COLOR = (0xE8, 0xB6, 0x4C)

SIZES = {
    "StoreLogo.png": (50, 50),
    "Square44x44Logo.png": (44, 44),
    "Square150x150Logo.png": (150, 150),
    "Wide310x150Logo.png": (310, 150),
    "SplashScreen.png": (620, 300),
}


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _png(path: Path, width: int, height: int, rgb: tuple[int, int, int]) -> None:
    row = b"\x00" + bytes(rgb) * width
    raw = row * height
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(payload)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, (w, h) in SIZES.items():
        _png(ASSETS / name, w, h, COLOR)
        print(f"wrote {ASSETS / name} ({w}x{h})")


if __name__ == "__main__":
    main()
