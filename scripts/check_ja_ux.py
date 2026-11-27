#!/usr/bin/env python3
"""Japanese UX smoke test — language switching, persistence and data names.

    python scripts/check_ja_ux.py --base http://localhost:47600

Exercises what a text sweep cannot: the 言語 selector, the ``?lang=`` override,
``hp.locale`` persistence across reloads, ``<html lang>``, and that captured
English monster names are re-localized in rows.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
DATA = json.loads((REPO / "dashboard/locales/ja/data.json").read_text("utf-8"))
JA_MONSTERS = {n for n in DATA.get("monsters", {}).values() if n}
CJK = re.compile(r"[ぁ-んァ-ン一-龯]")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--shots", default="/tmp/opencode/ja-ux")
    args = ap.parse_args(argv)
    base = args.base.rstrip("/")
    shots = Path(args.shots)
    shots.mkdir(parents=True, exist_ok=True)
    executable = os.environ.get("CHROME_PATH") or str(
        Path.home() / ".cache/ms-playwright/chromium-1228/chrome-linux64/chrome")

    checks: list[tuple[str, bool, str]] = []

    def check(label: str, ok: bool, extra: str = "") -> None:
        checks.append((label, ok, extra))
        print(f"{'v' if ok else 'x'} {label}{f' - {extra}' if extra else ''}")

    def dismiss_overlays(page) -> None:
        """The What's-new note opens once per version and blocks clicks."""
        for _ in range(3):
            if page.locator(".modal-backdrop").count() == 0:
                return
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=executable, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 1000})

        page.goto(f"{base}/?tab=hunts&lang=ja", wait_until="networkidle")
        page.wait_for_timeout(1500)
        dismiss_overlays(page)
        check("<html lang> is ja with ?lang=ja",
              page.evaluate("document.documentElement.lang") == "ja")

        nav = page.locator("nav.tabs button").all_inner_texts()
        check("tab labels are Japanese", any("ハント" in s for s in nav), " | ".join(nav[:4]))

        text = page.locator("main").inner_text()
        found = [n for n in JA_MONSTERS if n in text]
        check("monster names are localized in the Hunts tab", bool(found),
              ", ".join(found[:3]) or "no Japanese monster found")

        dismiss_overlays(page)
        # Search must match what is on screen: the localized monster name.
        target = found[0] if found else None
        if target:
            box = page.locator("label.hunt-search input")
            box.fill(target)
            page.wait_for_timeout(600)
            rows = page.locator("main table tbody tr")
            count = rows.count()
            first = rows.first.inner_text() if count else ""
            check(f"search matches the Japanese monster name ({target})",
                  count > 0 and target in first, f"{count} rows")
            box.fill("")
            page.wait_for_timeout(400)

        page.locator("button.settings-open").click()
        page.wait_for_timeout(500)
        check("language row exists",
              page.locator(".settings-page .seg button", has_text="日本語").count() > 0)
        page.screenshot(path=str(shots / "settings-ja.png"), full_page=True)

        page.locator(".settings-page button", has_text="English").first.click()
        page.wait_for_timeout(700)
        check("switching to English updates <html lang>",
              page.evaluate("document.documentElement.lang") == "en")
        nav_en = page.locator("nav.tabs button").all_inner_texts()
        check("tab labels switch to English", "Hunts" in nav_en, " | ".join(nav_en[:4]))
        check("preference persisted",
              page.evaluate("localStorage.getItem('hp.locale')") == "en")

        # An explicit switch must not be undone by the stale `?lang=ja` on
        # reload: setLocale clears the override.
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(1200)
        check("explicit switch survives a reload of the ?lang=ja URL",
              page.evaluate("document.documentElement.lang") == "en")

        page.locator("button.settings-open").click()
        page.wait_for_timeout(400)
        page.locator(".settings-page button", has_text="日本語").first.click()
        page.wait_for_timeout(700)
        page.keyboard.press("Escape")

        page.goto(f"{base}/?tab=hunts", wait_until="networkidle")
        page.wait_for_timeout(1300)
        dismiss_overlays(page)
        check("locale survives a reload without ?lang",
              page.evaluate("document.documentElement.lang") == "ja")

        # Buffs: the tab defaults to the newest hunt (which may have no buffs),
        # so only require that it renders instead of going blank.
        page.goto(f"{base}/?tab=buffs&lang=ja", wait_until="networkidle")
        page.wait_for_timeout(1600)
        dismiss_overlays(page)
        buffs_text = page.locator("main").inner_text()
        buffs_rows = page.locator("main table tbody tr").count()
        check("buffs tab renders (rows, or a hunt picked without buffs)",
              buffs_rows > 0 or len(buffs_text.strip()) > 60, f"{buffs_rows} rows")

        page.goto(f"{base}/?tab=hunts&lang=ja", wait_until="networkidle")
        page.wait_for_timeout(1200)
        dismiss_overlays(page)
        row = page.locator("main table tbody tr").first
        if row.count() > 0:
            row.click()
            page.wait_for_timeout(1300)
            dialog = page.locator("[role=dialog], .modal").inner_text()
            check("hunt dialog text is Japanese", bool(CJK.search(dialog)))
            page.screenshot(path=str(shots / "hunt-dialog-ja.png"), full_page=True)
            page.keyboard.press("Escape")
        else:
            check("hunt dialog (skipped: no rows)", True)
        browser.close()

    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed - screenshots in {shots}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
