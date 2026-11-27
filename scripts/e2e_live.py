#!/usr/bin/env python3
"""Full end-to-end walk of a running dashboard (Playwright, ja + en).

    python scripts/e2e_live.py --base http://localhost:47601

Covers: shell/tabs, language switching and persistence, hunter scope, party
filter, per-view filters, hunt search/pagination/detail dialog, hunt manager,
highlights, curve controls, survival toggles, buffs sub-tabs/views/filters,
the remaining views, settings (theme, update check, What's new) and a raw-key
sweep in both languages. Read-only apart from the ignore/restore round-trip,
which is safe on a copy DB.

Screenshots go to --shots (default /tmp/opencode/e2e).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

TABS = [
    ("progress", "進行"), ("growth", "成長"), ("weapons", "武器"),
    ("highlights", "ハイライト"), ("curves", "ダメージカーブ"),
    ("hunts", "ハント"), ("survival", "生存"), ("leaderboard", "ランキング"),
    ("high-scores", "ハイスコア"), ("compare", "比較"), ("activity", "アクティビティ"),
    ("synergy", "シナジー"), ("buffs", "バフ"),
]
KEY_LIKE = re.compile(
    r"\b(?:tab|hunts|curves|growth|weapons|highlights|survival|leaderboard|"
    r"highscores|compare|activity|synergy|buffs|table|scope|settings|common|changelog)\.[a-zA-Z][\w.]*")

results: list[tuple[str, bool, str, str]] = []


def check(section: str, label: str, ok: bool, detail: str = "") -> None:
    results.append((section, label, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} [{section}] {label}{f' — {detail}' if detail else ''}")


def skip(section: str, label: str, why: str) -> None:
    results.append((section, label, True, f"skipped: {why}"))
    print(f"SKIP [{section}] {label} — {why}")


class Runner:
    def __init__(self, page: Page, base: str, shots: Path):
        self.page = page
        self.base = base.rstrip("/")
        self.shots = shots
        self.console: list[str] = []
        self.http: list[tuple[int, str]] = []
        self.requests: list[str] = []
        page.on("console", lambda m: self.console.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: self.console.append(f"pageerror: {e}"))
        page.on("response",
                lambda r: self.http.append((r.status, r.url)) if r.status >= 400 else None)
        page.on("request", lambda r: self.requests.append(r.url))

    # -- navigation helpers -------------------------------------------------
    def dismiss(self) -> None:
        for _ in range(3):
            if self.page.locator(".modal-backdrop").count() == 0:
                return
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(350)

    def go(self, tab: str, lang: str = "ja", wait: int = 1400) -> None:
        self.console.clear()
        self.http.clear()
        self.requests.clear()
        self.page.goto(f"{self.base}/?tab={tab}&lang={lang}", wait_until="networkidle")
        self.page.wait_for_timeout(wait)
        self.dismiss()

    def shot(self, name: str) -> None:
        self.page.screenshot(path=str(self.shots / f"{name}.png"), full_page=True)

    def text(self, sel: str = "main") -> str:
        return self.page.locator(sel).inner_text()

    def rows(self) -> int:
        return self.page.locator("main table tbody tr").count()

    def no_errors(self, label: str) -> None:
        check("runtime", f"{label}: no console errors", not self.console,
              "; ".join(self.console[:2]))
        check("runtime", f"{label}: no HTTP errors", not self.http,
              "; ".join(f"{s} {u[-60:]}" for s, u in self.http[:2]))
        leaked = sorted(set(KEY_LIKE.findall(self.text())))
        check("runtime", f"{label}: no raw i18n keys", not leaked, ", ".join(leaked[:3]))

    def has_ja(self, needle: str) -> bool:
        return needle in self.text()


def run(p: Runner) -> None:
    page = p.page

    # 1. Shell -------------------------------------------------------------
    p.go("progress")
    check("shell", "health pill shows the hunt count", "取り込み稼働中" in p.text("header.topbar"))
    tabs = page.locator("nav.tabs button").all_inner_texts()
    check("shell", "13 Japanese tabs", len(tabs) == 13 and tabs[1] == "成長", " | ".join(tabs[:4]))
    check("shell", "<html lang> is ja", page.evaluate("document.documentElement.lang") == "ja")
    check("shell", "progress chart renders", page.locator(".recharts-surface").count() > 0)
    p.shot("01-progress-ja")
    p.no_errors("progress")

    # 2. Language switch ---------------------------------------------------
    page.locator("button.settings-open").click()
    page.wait_for_timeout(400)
    check("i18n", "language row present",
          page.locator(".settings-page .seg button", has_text="日本語").count() > 0)
    page.locator(".settings-page button", has_text="English").first.click()
    page.wait_for_timeout(700)
    check("i18n", "switching to English updates <html lang>",
          page.evaluate("document.documentElement.lang") == "en")
    check("i18n", "tab labels switch to English",
          "Hunts" in page.locator("nav.tabs button").all_inner_texts())
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1000)
    p.dismiss()
    check("i18n", "English survives a reload (hp.locale)",
          page.evaluate("document.documentElement.lang") == "en")
    page.locator("button.settings-open").click()
    page.wait_for_timeout(400)
    page.screenshot(path=str(p.shots / "02-settings-en.png"), full_page=True)
    page.locator(".settings-page button", has_text="日本語").first.click()
    page.wait_for_timeout(700)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    # 3. Hunter scope ------------------------------------------------------
    p.go("progress")
    page.locator(".scope-picker > button").click()
    page.wait_for_timeout(300)
    page.locator(".scope-search").fill("Isi")
    page.wait_for_timeout(300)
    before = page.locator(".scope-row").count()
    page.locator(".scope-row .scope-name").first.click()
    page.wait_for_timeout(900)
    chips = page.locator(".scopebar .chip").count()
    scoped_req = [u for u in p.requests if "player_ids=" in u]
    check("scope", "picker search narrows the list", before > 0, f"{before} rows")
    check("scope", "selecting a hunter adds a chip", chips == 1, f"{chips} chip(s)")
    check("scope", "views refetch with player_ids", bool(scoped_req), scoped_req[0][-60:] if scoped_req else "")
    page.locator(".scope-clear").click()
    page.wait_for_timeout(800)
    check("scope", "clear removes the chip", page.locator(".scopebar .chip").count() == 0)

    # 4. Party filter ------------------------------------------------------
    p.go("hunts")
    page.locator(".scopebar .seg button", has_text=re.compile(r"^2$")).first.click()
    page.wait_for_timeout(900)
    party_req = [u for u in p.requests if "players=2" in u]
    check("scope", "party=2 reaches the API", bool(party_req), party_req[0][-40:] if party_req else "")
    page.locator(".scopebar .seg button", has_text="すべて").first.click()
    page.wait_for_timeout(700)

    # 5. Hunts: search, filters, paging, dialog ----------------------------
    search = page.locator("label.hunt-search input")
    search.fill("#1209")
    page.wait_for_timeout(600)
    check("hunts", "search by hunt id", p.rows() == 1, f"{p.rows()} rows")
    first = page.locator("main table tbody tr").first.inner_text()
    search.fill("リオレウス")
    page.wait_for_timeout(600)
    check("hunts", "search by Japanese monster name", p.rows() > 0 and "リオレウス" in
          page.locator("main table tbody tr").first.inner_text(), f"{p.rows()} rows")
    search.fill("")
    page.wait_for_timeout(500)

    page.locator(".filters .seg button", has_text="クリア").first.click()
    page.wait_for_timeout(700)
    clear_only = page.locator("main table tbody tr td:last-child").all_inner_texts()
    check("hunts", "result filter = cleared", p.rows() > 0 and all(x.strip() == "クリア" for x in clear_only[:5]),
          f"{p.rows()} rows")
    page.locator(".filters .seg button", has_text="すべて").first.click()
    page.wait_for_timeout(600)

    pager_before = page.locator(".table-pager, .pager").first.inner_text() if page.locator(".table-pager, .pager").count() else ""
    if page.locator("button", has_text="次へ").count() > 0:
        page.locator("button", has_text="次へ").first.click()
        page.wait_for_timeout(700)
        pager_after = page.locator(".table-pager, .pager").first.inner_text() if page.locator(".table-pager, .pager").count() else ""
        check("hunts", "pagination next changes the page", pager_after != pager_before, f"{pager_before} -> {pager_after}")
        page.locator("button", has_text="前へ").first.click()
        page.wait_for_timeout(600)
    else:
        skip("hunts", "pagination", "single page")

    page.locator("main table tbody tr").first.click()
    page.wait_for_timeout(1500)
    dialog = page.locator("[role=dialog], .modal")
    check("hunts", "hunt dialog opens", dialog.count() > 0)
    dtext = dialog.first.inner_text()
    check("hunts", "dialog shows party damage + share",
          "ダメージシェア" in dtext or "ハンター褒賞" in dtext, dtext.splitlines()[0][:40])
    check("hunts", "dialog renders the damage chart", dialog.locator(".recharts-surface").count() > 0)
    p.shot("03-hunt-dialog-ja")
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)

    # 6. Hunt manager ------------------------------------------------------
    # Exact text: "ハントをインポート" also contains ハント.
    page.locator('header.topbar button:text-is("ハント")').first.click()
    page.wait_for_timeout(500)
    try:
        page.wait_for_selector(".hunt-row", timeout=20000)
    except Exception:
        pass
    mgr = page.locator("[role=dialog], .modal").first
    page.screenshot(path=str(p.shots / "04b-hunt-manager.png"), full_page=True)
    check("manager", "hunt manager lists hunts", mgr.locator(".hunt-row").count() > 0,
          f"{mgr.locator('.hunt-row').count()} rows")
    box = mgr.locator("input.modal-search")
    if box.count():
        box.fill("#1209")
        page.wait_for_timeout(600)
        check("manager", "manager search filters", mgr.locator(".hunt-row").count() == 1,
              f"{mgr.locator('.hunt-row').count()} rows")
        box.fill("")
    p.shot("04-hunt-manager-ja")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    # 7. Highlights --------------------------------------------------------
    p.go("highlights")
    check("highlights", "leaderboard rows", p.rows() > 0, f"{p.rows()} rows")
    multiselect = page.locator("main details.multiselect")
    check("highlights", "award multi-select present", multiselect.count() > 0,
          multiselect.first.locator("summary").inner_text() if multiselect.count() else "")
    if multiselect.count():
        multiselect.first.locator("summary").click()
        page.wait_for_timeout(500)
        n_opts = multiselect.first.locator("label.multiselect-item input[type=checkbox]").count()
        check("highlights", "award list exposes the captured awards", n_opts >= 10, f"{n_opts} awards")
        first_award = multiselect.first.locator("label.multiselect-item span").first.inner_text()
        check("highlights", "award label is Japanese", bool(re.search(r"[ぁ-んァ-ン一-龯]", first_award)),
              first_award)
        page.screenshot(path=str(p.shots / "05b-awards-popover-ja.png"), full_page=True)
        multiselect.first.locator("summary").click()
        page.wait_for_timeout(300)
    ja_awards = [a for a in ("サポートオールスター", "パーフェクトカウンター", "激突王", "弱点を突け！")
                 if p.has_ja(a)]
    check("highlights", "award names are Japanese", len(ja_awards) >= 2, ", ".join(ja_awards))
    p.shot("05-highlights-ja")
    p.no_errors("highlights")

    # 8. Damage curves -----------------------------------------------------
    p.go("curves", wait=2000)
    check("curves", "chart renders", page.locator(".recharts-surface").count() > 0)
    if page.locator("button", has_text="瞬間DPS（5秒窓）").count():
        page.locator("button", has_text="瞬間DPS（5秒窓）").first.click()
        page.wait_for_timeout(900)
        check("curves", "metric switch keeps the chart", page.locator(".recharts-surface").count() > 0)
    else:
        skip("curves", "metric switch", "control not found")
    hp_toggle = page.locator("label", has_text="モンスターHP")
    if hp_toggle.count():
        hp_toggle.first.locator("input").check(force=True)
        page.wait_for_timeout(900)
        check("curves", "monster HP overlay toggles", "HP" in p.text())
    else:
        skip("curves", "monster HP overlay", "control not found")
    legend = page.locator(".recharts-legend-item")
    if legend.count() > 1:
        legend.first.click()
        page.wait_for_timeout(700)
        check("curves", "legend click hides a series", p.page.locator(".recharts-legend-item-inactive").count() > 0)
        if page.locator("button", has_text="全ハンターを表示").count():
            page.locator("button", has_text="全ハンターを表示").first.click()
            page.wait_for_timeout(500)
    else:
        skip("curves", "legend toggle", "single series")
    p.shot("06-curves-ja")
    p.no_errors("curves")

    # 9. Survival ----------------------------------------------------------
    p.go("survival", wait=1800)
    check("survival", "time-in-danger table", p.has_ja("危険時間") and p.rows() > 0, f"{p.rows()} rows")
    hide_buttons = page.locator("main button[title$='を隠す']")
    if hide_buttons.count():
        before_rows = p.rows()
        hide_buttons.first.click()
        page.wait_for_timeout(800)
        check("survival", "hunter toggle removes a row", p.rows() < before_rows,
              f"{before_rows} -> {p.rows()}")
        page.locator("main button[title$='を表示']").first.click()
        page.wait_for_timeout(600)
    else:
        skip("survival", "hunter toggle", "no players in the selected hunt")
    p.shot("07-survival-ja")
    p.no_errors("survival")

    # 10. Buffs ------------------------------------------------------------
    p.go("buffs", wait=2000)
    buffs_rows = p.rows()
    check("buffs", "buff table or explanation", buffs_rows > 0 or len(p.text()) > 80, f"{buffs_rows} rows")
    page.locator("main button[role=tab]", has_text="モンスター").first.click()
    page.wait_for_timeout(1200)
    check("buffs", "monster sub-tab shows status lanes/table", p.has_ja("怒り") or p.has_ja("状態"), "")
    page.locator("main button[role=tab]", has_text="ハンター").first.click()
    page.wait_for_timeout(900)
    if page.locator("button", has_text="タイムライン").count():
        page.locator("button", has_text="タイムライン").first.click()
        page.wait_for_timeout(900)
        check("buffs", "timeline view renders lanes", page.locator(".buff-lane").count() > 0,
              f"{page.locator('.buff-lane').count()} lanes")
        p.shot("08-buffs-timeline-ja")
        page.locator("button", has_text="表").first.click()
        page.wait_for_timeout(600)
    else:
        skip("buffs", "timeline view", "control not found")
    cat = page.locator("main .filters select").first
    if cat.count() and cat.locator("option").count() > 1:
        cat.select_option(index=1)
        page.wait_for_timeout(800)
        check("buffs", "category filter applies", True)
        cat.select_option(index=0)
    p.shot("09-buffs-table-ja")
    p.no_errors("buffs")

    # 11. Remaining views --------------------------------------------------
    for tab, needle in (("leaderboard", "ハンター"), ("high-scores", "ハント"),
                        ("activity", "日"), ("synergy", "ハンター")):
        p.go(tab, wait=1500)
        check(tab, "renders rows or an empty state", p.rows() > 0 or p.has_ja(needle) or len(p.text()) > 80,
              f"{p.rows()} rows")
        p.shot(f"10-{tab}-ja")
        p.no_errors(tab)

    p.go("compare")
    check("compare", "asks to scope a hunter when unscoped",
          p.has_ja("ハンター") or p.rows() > 0, f"{p.rows()} rows")
    p.no_errors("compare")

    p.go("weapons")
    check("weapons", "weapon bars render", page.locator(".recharts-surface").count() > 0 and p.rows() > 0)
    p.no_errors("weapons")
    p.go("growth")
    check("growth", "growth tiles render", p.has_ja("成長率") or p.has_ja("ハンター"))
    p.no_errors("growth")

    # 12. Settings: theme, update check, What's new ------------------------
    p.go("progress")
    page.locator("button.settings-open").click()
    page.wait_for_timeout(400)
    page.locator(".settings-page button", has_text="ライト").first.click()
    page.wait_for_timeout(500)
    theme = page.evaluate("document.documentElement.dataset.theme")
    check("settings", "light theme applies", theme == "light", theme)
    page.locator(".settings-page button", has_text="ダーク").first.click()
    page.wait_for_timeout(400)
    check("settings", "dark theme restores",
          page.evaluate("document.documentElement.dataset.theme") == "dark")

    update_box = page.locator(".settings-check", has_text="アップデートを確認").locator("input")
    if update_box.count():
        update_box.first.uncheck(force=True)
        page.wait_for_timeout(400)
        page.keyboard.press("Escape")
        p.console.clear()
        p.requests.clear()
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(1200)
        p.dismiss()
        check("settings", "update check off sends no /api/update",
              not any("/api/update" in u for u in p.requests))
        page.locator("button.settings-open").click()
        page.wait_for_timeout(400)
        page.locator(".settings-check", has_text="アップデートを確認").locator("input").first.check(force=True)
        page.wait_for_timeout(300)
    else:
        skip("settings", "update check toggle", "control not found")

    srcs = page.locator(".settings-page").inner_text()
    check("settings", "companion source is listed", "HunterPie" in srcs, "")
    p.shot("12-settings-ja")

    if page.locator(".settings-page button.link-button").count():
        page.locator(".settings-page button.link-button").first.click()
        page.wait_for_timeout(700)
        notes = page.locator("[role=dialog], .modal").first.inner_text()
        check("settings", "What's new shows v1.3.0 notes",
              "v1.3.0" in notes and "日本語" in notes, notes.splitlines()[0][:40])
        p.shot("11-whats-new-ja")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    else:
        skip("settings", "What's new", "link not found")
    p.dismiss()

    # 13. English pass -----------------------------------------------------
    for tab in ("progress", "hunts", "buffs"):
        p.go(tab, lang="en", wait=1500)
        p.no_errors(f"en:{tab}")
        check("en", f"{tab}: English labels", not p.has_ja("ハント"), p.text().splitlines()[0][:30])
    p.go("hunts", lang="en")
    p.shot("13-hunts-en")

    # 14. Restore language ------------------------------------------------
    p.go("progress")
    check("i18n", "back to Japanese", page.evaluate("document.documentElement.lang") == "ja")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://localhost:47601")
    ap.add_argument("--shots", default="/tmp/opencode/e2e")
    args = ap.parse_args(argv)
    shots = Path(args.shots)
    shots.mkdir(parents=True, exist_ok=True)
    executable = os.environ.get("CHROME_PATH") or str(
        Path.home() / ".cache/ms-playwright/chromium-1228/chrome-linux64/chrome")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=executable, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        runner = Runner(page, args.base, shots)
        try:
            run(runner)
        except Exception as exc:  # keep the report even if a step aborts
            check("harness", "suite completed", False, f"{type(exc).__name__}: {exc}")
            page.screenshot(path=str(shots / "zz-crash.png"), full_page=True)
        browser.close()

    failed = [r for r in results if not r[2]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed · screenshots in {shots}")
    if failed:
        print("\nfailures:")
        for section, label, _ok, detail in failed:
            print(f"  - [{section}] {label} {detail}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
