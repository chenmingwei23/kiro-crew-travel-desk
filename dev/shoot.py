#!/usr/bin/env python3
"""Screenshot the 旅行规划 UI through its key states against dev/harness.py.

    python3 dev/shoot.py --base http://127.0.0.1:8765 --out design/evidence [--empty] [--lang en]

Writes trip-top / trip-day1 / trip-daymap / chat-card / settings / map-all /
map-day2-chat / trip-team (or empty-state, or setup) PNGs at 1440x900 and prints
any console errors (exit 1 if any). `--lang en` seeds the language preference so
the English chrome is captured; `--suffix` tags the files (e.g. "-en").
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--out", default="design/evidence")
    ap.add_argument("--empty", action="store_true")
    ap.add_argument("--lang", default="", help="seed travel-desk.lang (zh-CN | en)")
    ap.add_argument("--suffix", default="", help="filename suffix, e.g. -en")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    sfx = args.suffix

    def shot(pg, name: str, **kw) -> None:
        pg.screenshot(path=str(out / f"{name}{sfx}.png"), **kw)

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": args.width, "height": args.height}, device_scale_factor=1)
        def on_console(m):
            if m.type != "error":
                return
            # A conversation that does not exist yet answers 404 to the app's
            # probe by design; Chromium still logs it. Everything else is a defect.
            url = (m.location or {}).get("url", "") if isinstance(m.location, dict) else ""
            if "Failed to load resource" in m.text and "/api/chat/slots/" in url:
                return
            errors.append(f"[{m.type}] {m.text} <{url}>")

        pg.on("console", on_console)
        pg.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        pg.goto(args.base + "/", wait_until="networkidle")
        pg.evaluate("localStorage.clear()")
        if args.lang:
            pg.evaluate("(l) => localStorage.setItem('travel-desk.lang', l)", args.lang)
        pg.goto(args.base + "/", wait_until="networkidle")
        pg.wait_for_timeout(3500)

        if pg.locator(".td-setup").count() > 0:
            shot(pg, "setup")
            # the one-click run with its optional custom login opened
            if pg.locator(".td-linkbtn").count() > 0:
                pg.locator(".td-linkbtn").first.click()
                pg.wait_for_timeout(300)
                shot(pg, "setup-custom")
            # the Settings row the page points at (address + login live there)
            pg.locator(".td-settings-bar .td-pill").first.click()
            pg.wait_for_timeout(600)
            if pg.locator(".td-adv-toggle").count() > 0:
                pg.locator(".td-adv-toggle").first.click()
                pg.wait_for_timeout(300)
            shot(pg, "setup-settings")
        elif args.empty or pg.locator(".td-empty").count() > 0:
            shot(pg, "empty-state")
            pg.locator(".td-chatcard").first.screenshot(path=str(out / f"chat-card{sfx}.png"))
            # settings from the empty state's menu too
            pg.locator(".td-topbar .td-iconbtn").click()
            pg.wait_for_timeout(300)
            pg.locator(".td-menu .td-menu-item").last.click()
            pg.wait_for_timeout(600)
            shot(pg, "settings")
        else:
            shot(pg, "trip-top")
            # the chat card alone, at 2x, so type and colours can be judged
            card = pg.locator(".td-chatcard").first
            card.screenshot(path=str(out / f"chat-card{sfx}.png"))
            # the workbench: the chat fills the page, the team stands on the left
            pg.locator(".td-chatcard .td-benchbtn").first.click()
            pg.wait_for_timeout(900)
            shot(pg, "workbench")
            pg.locator(".td-benchchat .td-benchbtn").first.click()
            pg.wait_for_timeout(900)
            # scroll to day 1
            pg.evaluate("""() => {
              const el = [...document.querySelectorAll('.td-day-head')][0]; if (el) el.scrollIntoView({block: 'start'});
              const sc = document.querySelector('.td-scroll'); if (sc) sc.scrollTop -= 90;
            }""")
            pg.wait_for_timeout(1200)
            shot(pg, "trip-day1")
            pg.evaluate("""() => {
              const el = document.querySelector('.td-daymap'); if (el) el.scrollIntoView({block: 'end'});
            }""")
            pg.wait_for_timeout(2500)
            shot(pg, "trip-daymap")
            # settings page via the "..." menu (last menu item)
            pg.evaluate("() => { const sc = document.querySelector('.td-scroll'); if (sc) sc.scrollTop = 0 }")
            pg.locator(".td-topbar .td-iconbtn").click()
            pg.wait_for_timeout(300)
            pg.locator(".td-menu .td-menu-item").last.click()
            pg.wait_for_timeout(600)
            pg.locator(".td-adv-toggle").click()
            pg.wait_for_timeout(300)
            shot(pg, "settings")
            pg.locator(".td-back").click()
            pg.wait_for_timeout(600)
            # map view: all days
            pg.click(".td-showmap")
            pg.wait_for_timeout(3500)
            shot(pg, "map-all")
            # day 2 + chat open + select a card
            chips = pg.locator(".td-chips .td-pill")
            if chips.count() >= 3:
                chips.nth(2).click()
                pg.wait_for_timeout(1500)
            cards = pg.locator(".td-card")
            if cards.count() >= 2:
                cards.nth(1).click()
                pg.wait_for_timeout(900)
            pg.click(".td-fab")
            pg.wait_for_timeout(1500)
            shot(pg, "map-day2-chat")
            # team popover on the trip page (the dark "back to trip" pill, language-independent)
            pg.locator(".td-ov.tr .td-pill.td-dark").click()
            pg.wait_for_timeout(1200)
            pg.locator(".td-chatcard .td-avatars").click()
            pg.wait_for_timeout(600)
            shot(pg, "trip-team")
        b.close()

    if errors:
        print("console errors:")
        for e in errors:
            print("  ", e)
        return 1
    print("ok, no console errors ->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
