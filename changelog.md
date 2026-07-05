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

## 2026-07-05 — P2 (Sections + OML loft) DONE

- `make gate PHASE=p02` green (7 tests) + regress green (p00–p02). Built
  `backend/geometry/`: `sections.py` (scale + twist about declared axis +
  per-segment dihedral/sweep accumulation), `loft.py` (watertight OML loft +
  mirror), `airfoil_resolver.py` (name→canonical, reuses P1). Added 3 golden
  reference wings + committed expected volumes (provenance), and 3 edge configs
  (high taper / high twist / thin foil).
- R0/diagnostic finding that changed the construction (docs/r0_findings/p02.md):
  a SPLINE loft (`makeLoft ruled=False`) bulges ~3.1% outward between sections —
  exactly the ±3% volume-gate limit — and its volume is unstable with section
  count. Switched to POLYGON wires + `ruled=True`: loft volume matches the
  analytic prismatoid to <0.3%, is stable, and gives planar facets robust for
  P4+ booleans. (`ruled=True` with spline wires is wrong — uses only edge
  endpoints.)
- Trap the R0 probe caught: a misaligned/twisted loft can report
  `IsValid()==True` yet be geometrically wrong (volume 5x off). So the gate
  pairs watertightness with the volume-conservation band, and sections keep a
  consistent point order/start (canonical TE-start) by construction.
- Twist placement matches an independent hand-computed rotation about the
  declared axis to 0.0 mm (exact). Volume dev vs analytic estimate: golden
  0.20–0.38%, all watertight; all edge configs valid (no self-intersection).
- Git: work done on branch `phase/p02` (per-phase branch/PR flow, PR-based).
  P0+P1 committed as baseline on main (commit 1a001d4); remote switched to SSH.
- Fixed `scripts/run_regress.py`: it passed the literal glob
  `tests/gates/test_p00_*.py` to pytest via subprocess (no shell expansion),
  so pytest exited 2 on an unmatched path. Now expands gate files with
  `Path.glob` and fails LOUDLY if a phase marked passed in state.json has no
  matching gate file (rather than letting an empty/literal glob masquerade as
  a pass). Regress stays strict; the gate itself was always proper pytest —
  only the regress runner's glob handling was wrong. See docs/known_issues.md.
