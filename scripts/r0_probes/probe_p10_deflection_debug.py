#!/usr/bin/env python3
"""Debug the P10 gate's deflection-vertex mismatch (144mm divergence at
12.5deg) against an already-completed job via ?job=<uuid>, without
re-paying the ~26min build cost. Adds an explicit wait after
setDeflection (testing the React-state-timing-race hypothesis) and dumps
axis/matrix/vertex data at each step.
"""
import sys
import time

import httpx
from playwright.sync_api import sync_playwright

FRONTEND = "http://127.0.0.1:5731"
API = "http://127.0.0.1:8731"
JOB_ID = sys.argv[1] if len(sys.argv) > 1 else "761fc11e-97ba-4071-8b23-cb3814ccd51d"


def main() -> int:
    kin = httpx.get(f"{API}/jobs/{JOB_ID}/kinematics", timeout=10).json()
    print("kinematics:", kin)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        messages = []
        page.on("console", lambda msg: messages.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda exc: messages.append(f"[pageerror] {exc}"))

        page.goto(f"{FRONTEND}/?job={JOB_ID}", timeout=15000)
        time.sleep(6)

        cs_bodies = page.evaluate("window.__wingE2E.getCsBodyNames()")
        body_name = cs_bodies[0]
        print(f"body_name: {body_name}")

        rest = page.evaluate(
            "([n, i]) => window.__wingE2E.getVertexWorldPosition(n, i)", [body_name, 0]
        )
        print(f"rest: {rest}")

        angle_deg = kin["max_deflection_deg"] / 2.0
        page.evaluate("(d) => window.__wingE2E.setDeflection(d)", angle_deg)
        time.sleep(1.0)  # explicit wait — testing the React-state-timing-race hypothesis

        client_world = page.evaluate(
            "([n, i]) => window.__wingE2E.getVertexWorldPosition(n, i)", [body_name, 0]
        )
        print(f"client_world (after 1s wait): {client_world}")

        resp = httpx.post(
            f"{API}/jobs/{JOB_ID}/kinematics/sample",
            json={"body_name": body_name, "point_local": rest, "angle_deg": angle_deg},
            timeout=10.0,
        )
        server = resp.json()
        print(f"server response: {server}")

        dev = max(abs(a - b) for a, b in zip(client_world, server["point_world"]))
        print(f"deviation: {dev:.4f}mm at angle={angle_deg}")

        # Independent sanity check: hand-rotate `rest` in Python via the
        # exact axis from the manifest, using the SAME Rodrigues formula.
        import numpy as np
        p0 = np.array(kin["axis_p0"])
        d = np.array(kin["axis_dir"]); d = d / np.linalg.norm(d)
        theta = np.radians(angle_deg)
        v = np.array(rest) - p0
        v_rot = v * np.cos(theta) + np.cross(d, v) * np.sin(theta) + d * np.dot(d, v) * (1 - np.cos(theta))
        expected = p0 + v_rot
        print(f"independent python rotation of `rest`: {expected.tolist()}")
        print(f"  vs server: {server['point_world']} (should match closely)")
        print(f"  vs client: {client_world}")

        print("\n--- console messages (last 10) ---")
        for m in messages[-10:]:
            print(m)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
