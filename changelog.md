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

## 2026-07-07 — P4 refined per-station construction: audit fixes + test-architecture overhaul

- **Context**: a prior session (interrupted mid-work, then resumed by a
  different model) had already replaced P4-v1's cylinder-based cove/nose
  with the normative per-station axis-centered-arc construction (ADR-002)
  and rewritten the gate for it, but the work was uncommitted and untrusted
  — `artifacts/gates/p04.json` still held v1's stale metrics shape
  (`cove_nose_radii_mm`), meaning the refined construction had never
  actually produced a real recorded gate pass. Audited both `te_cut.py` and
  `cove_profile.py` in full before running anything further.
- **Bug found and fixed**: `build_nose_arc_points`'s two-arc + Hermite-blend
  branch (taken when `|Ru-Rl| > NOSE_RADII_MATCH_MM`) produced two
  consecutive duplicate points at each arc/blend junction — the blend's
  `tt=0`/`tt=1` samples landed exactly on the arc segments' own last/first
  point, which the arc segment already contributes. Zero-length polygon
  edges are a latent loft-degeneracy risk. Neither current device config
  exercises this branch (`Ru-Rl` stays under the 1.0mm match threshold for
  both), so it was invisible until now; fixed by sampling the blend on an
  open interval `(0,1)` instead of the closed one, and added a fast
  pure-numpy regression test (`test_two_arc_nose_branch_no_duplicate_points`,
  synthetic `StationFeet` forcing the branch) so it stays caught even though
  no config currently reaches it.
- **Gate test weaknesses found and fixed**: `test_cove_clearance_at_rest_
  and_deflected` sampled ALL CS vertices, including the flat spanwise
  end-caps that sit `gap_mm` from the wing by design (a separate, orthogonal
  clearance mechanism) — restricted sampling to vertices axially interior to
  `[2*gap, axis_len-2*gap]` so the pre-existing spanwise clearance can't be
  mistaken for the radial `COVE_CLEARANCE_MM` one. `test_nose_axis_centered`
  only checked `Ru/Rl > kernel_tol` (non-degeneracy, not axis-centering) —
  rewrote it to sample the ACTUAL built CS solid via a real OCC section at
  several interior stations, split the section into nose-arc vs. aft-skin
  regions by angle, and assert the nose region's points fall within
  `[min(Ru,Rl), max(Ru,Rl)] ± COVE_CLEARANCE_TOL_MM` of the axis — a check
  that can actually fail if the built solid disagrees with the construction,
  unlike re-evaluating the same formula that built the points.
- **Test architecture overhaul** (docs/known_issues.md): the gate's
  `cut_results` fixture built BOTH device configs unconditionally regardless
  of `-k` test selection, so every diagnostic hypothesis about
  `te_half_twisted`'s runtime cost a ~260s+ full rebuild of both configs to
  test. Replaced with: (1) **lazy, indirect-parametrized fixtures**
  (`cut_result`/`cut_result_fresh`, keyed per config stem via
  `pytest_generate_tests`) — a `-k te_half` run now never touches
  `te_half_twisted`; (2) a **disk build cache**
  (`tests/gates/geometry_cache.py`), keyed on `SHA256(config JSON +
  geometry-module source)`, storing only the raw pre-shard-filter boolean
  output as `.brep` (verified round-trip-exact for both single- and
  multi-solid shapes — `scripts/r0_probes/probe_brep_cache.py`,
  `docs/r0_findings/p04.md`) — `filter_shards`/sort/gap-volume/every gate
  assertion always recomputes fresh from the loaded shapes, so caching can
  only skip a boolean, never an assertion; (3) `te_cut.py` split into
  `build_te_cut_shapes` (expensive, cacheable, now timed per stage) and
  `finish_te_cut` (cheap, always fresh) to give the cache a clean seam; (4) a
  **slow tier** (`@pytest.mark.slow`, registered in pyproject.toml) that
  forces one real uncached rebuild per config every gate/regress run,
  proving the cache matches reality — `-m "not slow"` is for quick local
  iteration only, never for `make gate`/`make regress`; (5)
  `GEOMETRY_TEST_TIMEOUT_S = 600` (`tolerances.py`) via `pytest-timeout`,
  applied module-wide, so "hang vs. slow" is answered by a timeout firing (or
  not), never by watching a terminal; (6) `--durations=20` on every gate/
  regress invocation (Makefile, `scripts/run_regress.py`); (7) per-stage
  construction timings (`station_data`, `loft_regions`, `aft_boxes`,
  `wing_cut`, `cs_fuse`, `cs_common`) written to
  `artifacts/gates/p04_timings.json` on every real build.
- **Result of the (now instrumented, cached) investigation**:
  `te_half_twisted`'s earlier ">150s, no completion" was not a hang — cold
  construction takes ~145s (vs ~50s untwisted), 2-4x more expensive
  specifically in `BRepAlgoAPI_Cut`/`Common` (lofting and station analysis
  are identical between configs) — a real, twist-driven OCC boolean cost,
  not a construction defect. No construction-strategy change applied: no
  single construction boolean exceeds the ~120s investigate threshold, the
  whole gate completes in ~7min with 4x+ headroom under the 600s per-test
  budget, and the actual pain (every gate re-run rebuilding regardless of
  what changed) is what the cache fixes — see docs/known_issues.md
  ("Twisted/tilted device configs cost 2-4x more per boolean than
  untwisted") for the full number breakdown and why tuning fidelity down was
  rejected.
- `make gate PHASE=p04` green (17 tests, both configs) + `make regress`
  green (p00-p04). New rule (CLAUDE.md): never re-run a full geometry build
  to answer a question that instrumentation, the build cache, or a single
  parametrized test can answer instead.
