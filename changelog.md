# Changelog

Decision journal — not a diff log (git has the diffs). One entry per
meaningful change: what changed, why, and what it retired/added.

## 2026-07-05 — P0 kickoff

- Repo scaffolded per plan.md §0.4. Dev/gate execution happens on the
  `wingo.coder` Coder workspace (Docker + cadquery/gmsh installed there);
  this Mac is the git source of truth, synced via rsync. Local Mac has
  neither Docker nor a real OCP/Gmsh install, so per §0.2/F13 (never mock
  the boundary) all gates must run on the workspace.
- `docker-compose.yml` starts only `postgres` + `redis` for now — api/worker/
  report/frontend containers have no real code yet; their service blocks
  land in the phase that builds their first real image.
- P0 schema validation scope narrowed to config-checkable rules only (device
  window overlap/containment, hinge-vs-spar xc ordering, gap_mm vs
  tolerances, sandwich-stack-vs-min-thickness). Geometry-dependent rules from
  the §6 "P0 validation rules" paragraph (hinge-axis OML containment, joint
  bolt-angle/lip-flushness) are deferred to the gates plan.md itself assigns
  them to (P3, P11, P18).
- Dropped a separate "break station outside device window" check: segments
  partition the span with no gaps, so it's mathematically equivalent to the
  device-segment-containment check (a break can only fall strictly inside a
  device window when that window isn't contained in one segment) — a
  standalone check would have been unreachable dead code. Containment
  (`DEVICE_NOT_SEGMENT_CONTAINED`) covers both; noted in
  `backend/schema/validators.py`.
- Added `backend/airfoils/naca_thickness.py`: a minimal analytic NACA4/5
  thickness helper, standalone from the full P1 airfoil ingest/resample
  pipeline, needed only to evaluate the P0 sandwich-stack-vs-thickness rule
  (F15) before P1 exists.
- `make gate PHASE=p00` green on `wingo.coder`: 9 pytest tests pass, wrote
  `artifacts/gates/p00.json` (pass=true) + a `gate_results` row.

## 2026-07-05 — P1 (Airfoil subsystem) DONE

- `make gate PHASE=p01` green (8 tests) + regress green (p00, p01). Airfoil
  subsystem: `naca.py` (4/5-digit generators, open-TE coeff), `uiuc_ingest.py`
  (Selig/Lednicer auto-detect + quarantine), `resample.py` (cosine + blunt-TE
  wedge), `metrics.py`, `types.py`.
- Vendored a curated 29-file UIUC snapshot (18 Selig / 11 Lednicer) + 1
  deliberately-malformed quarantine fixture (`_quarantine_me.dat`). Fetched on
  the workspace (Mac is network-sandboxed) from the UIUC coord DB.
- R0 finding that changed the design: the Selig/Lednicer discriminator can't
  threshold at x>1.0 — published Selig TE x rounds marginally OVER 1.0
  (`naca23012.dat` = 1.00003). Moved threshold to 1.5 (safe gap between a
  ~1.0 TE coord and an integer point-count ≥5). Caught by the P1 smoke test
  before the gate, not after. Documented in docs/r0_findings/p01.md.
- Method finding: airfoil curves are near-vertical at the LE, so y-at-x
  comparison overstates deviation ~30x there. All "curves match" checks use
  geometric point-to-curve distance (`metrics.py`). With it, NACA-vs-published
  max dev = 1.8e-4 and resample round-trip = 1.7e-4 chord (both << 1e-3).
- Deferred to later phases (not P1): DB persistence of ingested airfoils to
  the `airfoils` table (schema exists since P0); `.dat` upload endpoint (API,
  post-P10). P1 is the in-memory pipeline the gate verifies.
- Fixed `scripts/run_regress.py`: it passed the literal glob
  `tests/gates/test_p00_*.py` to pytest via subprocess (no shell expansion),
  so pytest exited 2 on an unmatched path. Now expands gate files with
  `Path.glob` and fails LOUDLY if a phase marked passed in state.json has no
  matching gate file (rather than letting an empty/literal glob masquerade as
  a pass). Regress stays strict; the gate itself was always proper pytest —
  only the regress runner's glob handling was wrong. See docs/known_issues.md.
