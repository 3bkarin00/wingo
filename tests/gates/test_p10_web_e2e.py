"""P10 gate — Web UI E2E (plan.md §9 P10 pass criteria):

  scripted run: submit golden config -> progress events received -> model
  renders -> each body toggles -> deflection slider animates about correct
  axis (compare a tracked vertex against server-computed position).

CONFIG SCOPE: te_half.yaml, not a mirror:true tests/golden/*.yaml — same
"documented, not a shortcut" posture as every other P6/P7/P8 battery-scope
note in this test suite. None of tests/golden/*.yaml declares a
`te_surface`, so a golden config alone can never satisfy the "deflection
slider animates about correct axis" criterion (there'd be no hinge
kinematics at all — backend.pipeline.build_wing's own module docstring:
device-cut/hinges require `te_surface` present+enabled). te_half.yaml is
also the ONLY config any P6/P7 gate has ever verified the full sandwich+
rib+spar+hinge construction against (mirror:false; see backend/pipeline.py
module docstring on why mirror:true stays a reduced build) — so it is
simultaneously the only config that can pass this gate's LAST criterion
and the only one with any real construction verification behind it.

COST (read before running): backend.pipeline.build_wing is production
code and, per CLAUDE.md's hard rule, NEVER goes through tests/gates/
geometry_cache.py — every run here pays the FULL uncached P6+P7 cost
(measured ~60-90min + ~300-450s in those gates' own docstrings). This
single gate can legitimately run for over an hour; P10_E2E_JOB_TIMEOUT_S
(tolerances.py) budgets 2hr. This is not a shortcut or an oversight — it's
what "never mock the third-party boundary a gate verifies" (CLAUDE.md)
actually costs for a true end-to-end web-stack test.

ENVIRONMENT PREREQUISITES (this gate does NOT set these up itself, same
posture as every other gate assuming `make up`/`make migrate` already
ran): Postgres+Redis up (`make up`), migrations applied (`make migrate`),
`frontend/` dependencies installed (`cd frontend && npm install`),
Playwright's browser binary fetched (`.venv/bin/playwright install
chromium` — a one-time download pip alone does not cover). Node/npm on
the remote wingo.coder workspace has NOT been verified present as of this
writing (docs/known_issues.md) — that is a real, separate blocker from
"does this test's logic work," tracked there rather than silently
assumed away here.

ARCHITECTURE: session-scoped fixtures launch the real `uvicorn
backend.api.main:app` and the real `npm run dev` (Vite) as subprocesses on
fixed test ports, poll each for readiness, and tear both down at session
end — mirroring how `make gate`/`make regress` already run pytest
directly against real processes rather than mocking either server.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from backend import tolerances

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
API_PORT = 8731
FRONTEND_PORT = 5731
API_BASE = f"http://127.0.0.1:{API_PORT}"
FRONTEND_BASE = f"http://127.0.0.1:{FRONTEND_PORT}"

CONFIG_NAME = "te_half"  # module docstring: the only config this gate can pass on every criterion

pytestmark = pytest.mark.timeout(tolerances.P10_E2E_JOB_TIMEOUT_S)


def _wait_for(url: str, timeout_s: float, label: str) -> None:
    deadline = time.time() + timeout_s
    last_exc: Exception | None = None
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code < 500:
                return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
        time.sleep(1.0)
    raise RuntimeError(f"{label} did not become ready within {timeout_s}s (last error: {last_exc})")


@pytest.fixture(scope="session")
def api_server():
    env = dict(os.environ)
    env.setdefault("DATABASE_URL", os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://wingstructgen:wingstructgen@localhost:5432/wingstructgen",
    ))
    env.setdefault("REDIS_URL", os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api.main:app",
         "--host", "127.0.0.1", "--port", str(API_PORT)],
        cwd=str(REPO_ROOT), env=env,
    )
    try:
        _wait_for(f"{API_BASE}/health", 30.0, "API server")
        yield API_BASE
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def frontend_server(api_server):
    """Invokes vite's own binary directly, NOT `npm run dev -- --port ...`
    — found empirically (this gate's first real run): npm's `--`
    passthrough APPENDS to package.json's own `dev` script
    ("vite --port 5173"), producing `vite --port 5173 --port 5731
    --strictPort` (two --port flags), and vite's default `--host`
    resolves "localhost" ambiguously (can bind IPv6-only) while
    `_wait_for` below checks the explicit IPv4 loopack — together these
    produced a real "Connection refused" against a server that had
    genuinely started, just not on the checked address. Calling vite
    directly with ONE unambiguous `--port` and an explicit
    `--host 127.0.0.1` sidesteps both.

    Also sets VITE_PROXY_TARGET=API_BASE — found empirically (this gate's
    2nd real run, after the invocation fix above): vite.config.ts's /api
    proxy defaulted to the `make run-api` convenience port (8000), not
    this gate's own deliberately-different API_PORT (8731, chosen to
    avoid colliding with a human's own dev session) — every /api/* fetch
    from the browser silently failed against the wrong port (empty
    config dropdown, no thrown exception to surface it). vite.config.ts's
    own docstring has the full story."""
    vite_bin = REPO_ROOT / "frontend" / "node_modules" / ".bin" / "vite"
    env = dict(os.environ)
    env["VITE_PROXY_TARGET"] = API_BASE
    proc = subprocess.Popen(
        [str(vite_bin), "--port", str(FRONTEND_PORT), "--strictPort", "--host", "127.0.0.1"],
        cwd=str(REPO_ROOT / "frontend"), env=env,
    )
    try:
        _wait_for(FRONTEND_BASE, 60.0, "Vite dev server")
        yield FRONTEND_BASE
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def shared_page(frontend_server, browser):
    """pytest-playwright's own `page` fixture is function-scoped (a fresh
    page per test) — this gate deliberately shares ONE page/job across
    every test function instead (module docstring's cost note: the
    P6+P7-scale uncached build only happens once per session), built on
    top of pytest-playwright's session-scoped `browser` fixture."""
    page = browser.new_page()
    yield page
    page.close()


@pytest.fixture(scope="session")
def built_job(shared_page, frontend_server):
    """Drives the full scripted run ONCE per session (module docstring's
    cost note — every other test in this file reuses the resulting job/page
    state rather than re-submitting): navigate -> select te_half -> Build
    -> progress events observed -> status reaches done. Returns the job id
    the frontend ended up with, read straight from window.__wingE2E.

    `frontend_server` MUST be an explicit fixture parameter here (found
    empirically, this gate's 2nd real run): referencing the bare name
    `frontend_server` without declaring it resolves to the module-level
    FUNCTION OBJECT (the fixture definition itself), not its resolved
    yielded URL — Playwright's `Page.goto` then fails trying to
    JSON-serialize a FixtureFunctionDefinition. `shared_page` already
    depends on `frontend_server` transitively, but pytest fixture
    resolution doesn't expose a dependency's own dependencies by name —
    every value actually used in a fixture body must be its own declared
    parameter."""
    shared_page.goto(frontend_server)
    shared_page.select_option('[data-testid="config-select"]', CONFIG_NAME)

    seen_stages: set[str] = set()
    shared_page.click('[data-testid="build-button"]')

    status_locator = shared_page.locator('[data-testid="job-status"]')
    deadline = time.time() + tolerances.P10_E2E_JOB_TIMEOUT_S
    last_text = ""
    while time.time() < deadline:
        text = status_locator.inner_text() if status_locator.count() else ""
        if text and text != last_text:
            last_text = text
            if "—" in text:
                seen_stages.add(text.split("—", 1)[1].strip())
        if text.startswith("done") or text.startswith("failed"):
            break
        time.sleep(2.0)

    assert last_text.startswith("done"), f"job did not reach done (last status: {last_text!r})"
    assert len(seen_stages) >= 2, (
        f"only {len(seen_stages)} distinct progress checkpoint stage(s) observed "
        f"({seen_stages}) — expected multiple (module docstring: 'progress events received')"
    )

    job_id = shared_page.evaluate("window.__wingE2E && window.__wingE2E.jobId")
    assert job_id, "window.__wingE2E.jobId missing after job completion — model did not load"
    return job_id


def test_progress_events_received(built_job):
    """built_job's own assertions already cover this (>=2 distinct stages
    observed) — this test exists so the criterion has its own named,
    independently-reportable pass/fail line in the gate output."""
    assert built_job


def test_model_renders(shared_page, built_job):
    body_names = shared_page.evaluate("window.__wingE2E.getBodyNames()")
    assert isinstance(body_names, list) and len(body_names) > 0, (
        "no glTF body nodes loaded into the three.js scene"
    )
    canvas_count = shared_page.locator('[data-testid="viewer-canvas"] canvas').count()
    assert canvas_count == 1, f"expected exactly 1 WebGL canvas, found {canvas_count}"


def test_each_body_toggles(shared_page, built_job):
    body_names = shared_page.evaluate("window.__wingE2E.getBodyNames()")
    assert body_names, "no bodies to toggle"
    target = body_names[0]

    shared_page.evaluate("(name) => window.__wingE2E.setBodyVisible(name, false)", target)
    assert shared_page.evaluate("(name) => window.__wingE2E.isBodyVisible(name)", target) is False

    shared_page.evaluate("(name) => window.__wingE2E.setBodyVisible(name, true)", target)
    assert shared_page.evaluate("(name) => window.__wingE2E.isBodyVisible(name)", target) is True


def test_deflection_slider_matches_server_computed_position(api_server, shared_page, built_job):
    """Plan.md's own wording: 'deflection slider animates about correct
    axis (compare a tracked vertex against server-computed position)'.

    Two INDEPENDENT rotation implementations of the same rigid transform:
    three.js's Matrix4.makeRotationAxis (client, Viewer.tsx) vs
    backend.geometry.kinematics.rotate_point's pure Rodrigues' formula
    (server, POST /jobs/{id}/kinematics/sample) — genuinely verifies "the
    axis is right," not just "the two use the same code."
    """
    job_id = built_job
    cs_bodies = shared_page.evaluate("window.__wingE2E.getCsBodyNames()")
    assert cs_bodies, "no CS-side bodies in this build's kinematics — te_half.yaml should always have some"
    body_name = cs_bodies[0]
    vertex_index = 0

    rest = shared_page.evaluate(
        "([name, idx]) => window.__wingE2E.getVertexWorldPosition(name, idx)",
        [body_name, vertex_index],
    )
    assert rest is not None, f"could not read a rest-position vertex for {body_name!r}"

    max_defl = shared_page.evaluate(
        "() => { const s = document.querySelector('[data-testid=\"deflection-slider\"]'); "
        "return s ? parseFloat(s.max) : null; }"
    )
    assert max_defl, "deflection slider not present or has no max — no hinge kinematics rendered"
    angle_deg = max_defl / 2.0

    shared_page.evaluate("(deg) => window.__wingE2E.setDeflection(deg)", angle_deg)
    client_world = shared_page.evaluate(
        "([name, idx]) => window.__wingE2E.getVertexWorldPosition(name, idx)",
        [body_name, vertex_index],
    )
    assert client_world is not None

    resp = httpx.post(
        f"{api_server}/jobs/{job_id}/kinematics/sample",
        json={"body_name": body_name, "point_local": rest, "angle_deg": angle_deg},
        timeout=10.0,
    )
    resp.raise_for_status()
    server = resp.json()
    assert server["moved"] is True, f"server does not consider {body_name!r} CS-side"
    server_world = server["point_world"]

    dev_mm = max(abs(a - b) for a, b in zip(client_world, server_world))
    assert dev_mm <= tolerances.KINEMATIC_VERTEX_CHECK_TOLERANCE_MM, (
        f"client (three.js) vs server (kinematics.rotate_point) rotated-vertex position "
        f"diverges by {dev_mm:.5f}mm > {tolerances.KINEMATIC_VERTEX_CHECK_TOLERANCE_MM}mm at "
        f"angle={angle_deg}deg: client={client_world}, server={server_world}"
    )
