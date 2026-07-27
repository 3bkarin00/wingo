#!/usr/bin/env python3
"""Debug why window.__wingE2E.getBodyNames() returned [] in the real P10
gate run, WITHOUT re-paying a ~26min job build: navigates directly to
?job=<id> for an already-completed job (App.tsx's new debug-load feature)
and captures every console message / page error.
"""
import sys
import time

from playwright.sync_api import sync_playwright

FRONTEND = "http://127.0.0.1:5731"
JOB_ID = sys.argv[1] if len(sys.argv) > 1 else "3179d01a-0158-465b-8334-c895791af1b0"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        messages = []
        page.on("console", lambda msg: messages.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda exc: messages.append(f"[pageerror] {exc}"))

        page.goto(f"{FRONTEND}/?job={JOB_ID}", timeout=15000)
        time.sleep(8)  # let the glTF fetch/parse settle

        body_names = page.evaluate("window.__wingE2E ? window.__wingE2E.getBodyNames() : 'NO_HOOK'")
        print(f"getBodyNames(): {body_names}")

        manifest_bodies = page.evaluate(
            "() => { try { return document.querySelector('[data-testid=\"viewer-canvas\"]') ? 'viewer mounted' : 'viewer NOT mounted'; } catch(e) { return String(e); } }"
        )
        print(f"viewer mount check: {manifest_bodies}")

        print("\n--- console/page messages ---")
        for m in messages:
            print(m)

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
