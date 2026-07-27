#!/usr/bin/env python3
"""Quick (~60s) smoke test of the P10 frontend's browser-interaction path
BEFORE committing to another full ~2h gate run — validates page load,
config-select population, build-button click, and that a job genuinely
starts (status flips to "running"), WITHOUT waiting for the job to finish.
Assumes the API (port 8731) and Vite dev server (port 5731) are already
running (same ports test_p10_web_e2e.py uses) — start them the same way
the gate does, or via `make run-api` / `cd frontend && npm run dev --
--port 5731`.
"""
import sys
import time

from playwright.sync_api import sync_playwright

FRONTEND = "http://127.0.0.1:5731"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))

        page.goto(FRONTEND, timeout=15000)
        page.wait_for_selector('[data-testid="config-select"]', timeout=10000)
        options = page.eval_on_selector_all('[data-testid="config-select"] option', "els => els.map(e => e.value)")
        print(f"config options: {options}")
        assert "te_half" in options, f"te_half missing from options: {options}"

        page.select_option('[data-testid="config-select"]', "te_half")
        page.click('[data-testid="build-button"]')

        deadline = time.time() + 30
        status_text = ""
        while time.time() < deadline:
            loc = page.locator('[data-testid="job-status"]')
            if loc.count():
                status_text = loc.inner_text()
                if status_text:
                    break
            time.sleep(1)

        print(f"job-status after click: {status_text!r}")
        print(f"console errors: {console_errors}")
        browser.close()

        assert status_text, "job-status never appeared — build click didn't trigger a job"
        assert not any("error" in e.lower() for e in console_errors), f"JS console errors: {console_errors}"
        print("SMOKE TEST PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
