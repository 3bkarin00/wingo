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

## 2026-07-05 — P4 (TE surface cut) DONE

- `make gate PHASE=p04` green (8 tests) + regress green (p00–p04). Built
  `backend/geometry/te_cut.py` + shared `booleans.py` (fuzzy cut/common, shard
  filter, coaxial-cylinder-radius extractor). New half-wing device configs
  (`tests/configs/devices/te_half*.yaml`, mirror:false → exactly 2 bodies).
- R0 probe (docs/r0_findings/p04.md) confirmed `.cut()`→Compound, `.Solids()`
  extraction, `SetFuzzyValue`, tilted-axis cylinders, shard behaviour. The
  construction it enabled: two nested cylinders about the tilted hinge axis
  (nose R, cove R+gap) + an aft half-space box. CS = OML ∩ (nose ∪ aft_box,
  inset span, aft plane pushed back by gap_mm); wing = OML − cove − aft_box
  (full span). CS ⊆ removed-from-wing region ⇒ disjoint ⇒ **volume conserved
  by set algebra (0.0000% error), not luck.**
- F4 (tangent-face) check: solid↔solid distance was too slow (>2min timeout),
  so the gate instead reads the ACTUAL built cove/nose cylinder radii off the
  geometry and asserts they're distinct (concentric-but-unequal ⇒ never
  tangent). Doubles as verifying the nose was rebuilt as a revolution. Real
  radii: cove 5.47 / nose 3.97 mm (te_half), gap = exactly 1.5 mm.
- Results: both configs 2 watertight bodies, 0 shards, 0.0% conservation
  error, non-tangent cove clearance. Scoping: device mirroring onto both wings
  deferred (P4/P5 use half-wing configs to match the plan's exact body counts).

## 2026-07-05 — P3 (Reference geometry) DONE

- `make gate PHASE=p03` green (16 tests) + regress green (p00–p03). Built
  `backend/geometry/reference.py`: spar ruled surfaces, rib planes (auto +
  forced at segment boundaries and device edges), TE/LE hinge axes (straight
  lines), fuselage hardpoints. 2 new edge configs (`devices_full`,
  `devices_twisted` — the deliberate F5 high-twist stress case).
- **Correctness bug found and fixed before marking the gate green**: the P3
  work existed uncommitted on this branch already, but its containment test
  only checked point-in-solid (`BRepClass3d_SolidClassifier` IN/ON) — which
  says nothing about *how far* inside a point is. A hinge axis sitting
  exactly at the skin (zero clearance) would have passed. Backfilled the
  missing R0 probe (docs/r0_findings/p03.md) for the new OCP APIs this phase
  touches, which surfaced the real fix: `BRepExtrema_DistShapeShape` between
  a vertex and a **solid** is always 0 for interior points (vertex-in-volume
  trivially "touches"); the true point-to-surface margin needs distance to
  the solid's **shell** (`oml.Shells()[0]`). Rewrote the gate to assert
  `distance-to-shell >= sandwich stack` (§9 P3 pass criteria, F5), not just
  containment. Real margins recorded: devices_twisted TE hinge margin drops
  from 5.85mm (untwisted) to 5.43mm (-12° twist) as physically expected, both
  comfortably clear of the 2.8mm required stack — not a threshold-skimming
  pass.
- Also fixed while reviewing: a bare `1e-5` tolerance literal in the gate
  test (moved to reusing `tolerances.KERNEL_TOLERANCE_MM` — no new literal
  needed); promoted `_PLY_THICKNESS_MM_PROVISIONAL` from a validators.py
  private dict to `tolerances.PLY_THICKNESS_MM_PROVISIONAL` so the P0
  validator and P3 gate can't drift apart on the same material assumption;
  made `sections.py`'s `interp_station`/`le_and_z_offset` and
  `resample.py`'s `interp_surface` public (reference.py needed them —
  reaching into another module's underscore-private names was the wrong
  fix); removed a stray uncommitted `scripts/test_reference.py` dev script
  (duplicated reference.py logic, not a real R0 probe).
