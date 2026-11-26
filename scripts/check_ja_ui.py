#!/usr/bin/env python3
"""Japanese UI sweep — run against a live dashboard (dev server or packaged build).

    python scripts/check_ja_ui.py --base http://localhost:47600

For every tab it loads ``?lang=ja``, screenshots the page, collects console
errors and lists Latin-script words still visible. Player names, brands and
units are expected; anything else is probably an untranslated string.

Requires the Playwright chromium build (``~/.cache/ms-playwright``), overridable
with ``CHROME_PATH``.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

TABS = [
    "progress", "growth", "weapons", "highlights", "curves", "hunts", "survival",
    "leaderboard", "high-scores", "compare", "activity", "synergy", "buffs",
]

#: Words that legitimately stay Latin in the Japanese UI.
ALLOW = {
    "DPS", "HP", "HR", "Mod", "MOD", "HunterPie", "REFramework", "HuntDumper",
    "Nexus", "GitHub", "CSV", "JSON", "ModOrganizer", "MO2", "OK", "PS", "IPC",
    "GPU", "CPU", "NPC", "MRP",
}


def looks_allowed(word: str) -> bool:
    import re

    if word in ALLOW:
        return True
    if re.fullmatch(r"v?\d+(\.\d+)*", word):
        return True
    if re.fullmatch(r"\d+[a-zA-Z]", word):
        return True
    return len(word) <= 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--shots", default="/tmp/opencode/ja-shots")
    ap.add_argument("--lang", default="ja")
    args = ap.parse_args(argv)

    base = args.base.rstrip("/")
    shots = Path(args.shots)
    shots.mkdir(parents=True, exist_ok=True)
    executable = os.environ.get("CHROME_PATH") or str(
        Path.home() / ".cache/ms-playwright/chromium-1228/chrome-linux64/chrome")

    failures = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=executable, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors: list[str] = []

        def on_console(m):
            if m.type == "error":
                errors.append(m.text)

        def on_pageerror(e):
            errors.append(f"pageerror: {e}")

        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        for tab in TABS:
            errors.clear()

            page.goto(f"{base}/?tab={tab}&lang={args.lang}", wait_until="networkidle")
            page.wait_for_timeout(1200)
            # The What's-new note opens once per version and covers the page.
            for _ in range(2):
                if page.locator(".modal-backdrop").count() == 0:
                    break
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)

            lang = page.evaluate("document.documentElement.lang")
            text = page.evaluate("document.body.innerText")
            import re

            words = sorted({
                w for w in re.findall(r"[A-Za-z][A-Za-z0-9'&._-]{2,}", text)
                if not looks_allowed(w)
            })
            page.screenshot(path=str(shots / f"{tab}.png"), full_page=True)
            tab_errors = list(errors)

            bad_lang = lang != args.lang
            failures += int(bad_lang) + int(bool(tab_errors))
            mark = "x" if bad_lang else "v"
            print(f"{mark} {tab:<12} lang={lang:<3} latin={len(words):<3} errors={len(tab_errors)}")
            for w in words:
                print(f"      . {w}")
            for e in tab_errors:
                print(f"      ! {e}")
        browser.close()

    print(f"\nscreenshots: {shots}")
    if failures:
        print(f"{failures} tab(s) had a wrong <html lang> or console errors", file=sys.stderr)
        return 1
    print("all tabs loaded in the requested language with no console errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
