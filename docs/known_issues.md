# Known Issues — OCC/Gmsh/ezdxf workaround knowledge base

Every resolved kernel fight gets an entry here. Format:

```
## <symptom, short>
- Root cause: ...
- Workaround: ...
- Phase found: pXX
```

Compounds in value toward P15–P16 (molds — the hardest OCC work). Skim the
entries relevant to a phase's libraries before starting that phase's
implementation (session protocol, CLAUDE.md).

## OCP/gmsh ImportError: libGL.so.1 / libXcursor.so.1 missing

- Root cause: `cadquery-ocp` links against libGL (via OpenCASCADE's
  visualization toolkit, even for headless boolean/geometry ops with no
  rendering involved); `gmsh`'s wheel similarly links X11 cursor/render
  libs. A bare Ubuntu 24.04 container/workspace has neither — pip installs
  the Python packages fine, but the native `.so` fails to `dlopen` at import
  time.
- Workaround: `sudo apt-get install -y libgl1 libglu1-mesa libxrender1
  libxext6 libxcursor1 libxinerama1 libxft2 libxrandr2 libxi6` on the
  workspace before running anything that imports `cadquery`/`OCP`/`gmsh`.
  Consider baking this into the Coder workspace image/dotfiles so future
  workspace rebuilds don't need to rediscover it.
- Phase found: p00 (R0 probes, `docs/r0_findings/p00.md`).

## Unmatched shell glob reaches pytest as a literal path

- Root cause: a glob pattern (e.g. `tests/gates/test_p00_*.py`) passed to
  `subprocess.run([pytest, pattern])` is NOT shell-expanded — pytest receives
  the literal string with the `*` in it and exits 2 ("file or directory not
  found"). The Makefile `gate` target worked only because make runs the
  pattern through a shell that expands it; `scripts/run_regress.py` used
  subprocess with no shell, so the same pattern failed.
- Workaround: always expand gate-file globs in Python (`Path.glob`) before
  handing concrete paths to pytest, and guard with an existence check — if a
  phase is marked passed in state.json but no gate file matches, fail loudly
  rather than let an empty/literal glob leak through and masquerade as a pass.
- Phase found: p00 (`scripts/run_regress.py`).

## Twisted/tilted device configs cost 2-4x more per boolean than untwisted

- Root cause: measured directly (artifacts/gates/p04_timings.json, cold
  cache) — `te_half` (untwisted, sweep/dihedral=0) vs `te_half_twisted`
  (-8° tip twist): `wing_cut_s` 28.6s -> 60.2s (2.1x), `cs_common_s` 20.0s ->
  83.7s (4.2x). Lofting (`loft_regions_s`) and per-station analytic
  sectioning (`station_data_s`) are IDENTICAL between the two configs
  (0.53s, 0.02s) — the cost is entirely in `BRepAlgoAPI_Cut`/`Common`
  themselves, not in anything P4's per-station arc construction controls.
  Twist tilts the station cutting planes relative to the OML's own ruled
  facets, so the boolean's face-face intersection curves are more numerous
  and less axis-aligned — a standard OCC cost driver, not a construction
  defect. Separately, `test_no_interbody_tangency`'s OWN verification
  boolean (wing ∩ CS on the two FINAL trimmed solids, independent of
  construction) hit 126.2s on the twisted config — the single largest
  number measured, technically over the "~120s" investigate threshold, but
  it is a deliberate F4 safety check (not something to weaken for speed)
  and still sits well inside the per-test budget.
- Workaround: NONE applied — no construction-strategy change met the bar
  for one. Rationale: no single CONSTRUCTION boolean exceeds ~120s (60.2s
  and 83.7s both under it); total per-config time (145s construction,
  470s for all 8 tests incl. a forced-fresh rebuild) sits well inside
  `tolerances.GEOMETRY_TEST_TIMEOUT_S` (600s, ~4x headroom on the single
  slowest test). The actual pain this was diagnosed for — every gate
  re-run paying this cost regardless of what changed — is fixed by the
  geometry build cache (`tests/gates/geometry_cache.py`), which makes an
  unchanged config+code re-run cost under a second. Tuning fidelity down
  (fewer stations, coarser sections, looser fuzzy value) to shave a
  one-time cold-build cost that no longer sits in the iteration loop would
  trade real geometric precision for a problem that's already solved —
  revisit ONLY if a future config's cold build actually approaches the
  600s budget (start with `fuzzy_cut`/`fuzzy_common`'s FuzzyValue on just
  that config, per plan.md's own F4 guidance, before touching station/arc
  density).
- Phase found: p04 (`docs/r0_findings/p04.md`, geometry-cache test
  architecture decision, changelog.md).

## P6 sandwich-shell booleans: hollow_common dominates, and identical boolean workloads vary ~4.6x run-to-run

- Root cause (two separate observations, both from the same instrumented
  measurements — `SandwichLofts.timings_s`/`SandwichBody.timings_s` in
  `backend/geometry/iml.py`, on `te_half_twisted_moderate.yaml`):
  1. **Cost ranking within iml.py**: the per-station wire offsets and both
     ruled lofts are trivial (0.06s + 0.85s TOTAL). The entire cost is the
     three downstream booleans, and they are far from equal:
     `face_sheet_cut` (wing − face_IML) 226.9s, `core_cut` (face_IML −
     hollow_IML) 33.9s, `hollow_common` (wing ∩ hollow_IML) **370.2s —
     ~59% of the total on its own**. Two thin nearly-parallel offset
     shells intersecting a full device-cut body is exactly the
     near-coincident-face geometry OCC booleans are slowest at.
  2. **Run-to-run variance on the workspace**: the SAME three booleans,
     same config, same code, same machine, fresh process both times,
     measured 136.6s in one run and 631.0s in another (~4.6x) — with no
     other significant load visible (load avg ~1, single process at
     ~100% CPU). OCC boolean wall-time on this shared Coder VM is NOT a
     stable quantity.
- Workaround: (1) `build_sandwich_body(include_hollow_interior=False)`
  skips the hollow_common boolean for callers that only need the two
  shells — the dev viewer export uses this (it renders only the shells);
  the real P6 pipeline always computes it (ribs/spars are built inside
  the hollow interior). (2) Never treat a single wall-clock measurement
  as a config's true cost, and never use a wall-clock ratio between two
  RUNS as evidence of a code regression — compare per-stage `timings_s`
  ratios within the same run instead. A "gate suddenly got 4x slower"
  observation on this workspace is noise until the per-stage breakdown
  says otherwise.
- Phase found: p06 (viewer-export integration of `backend/geometry/iml.py`).

## cq.Shape.tessellate() doesn't dedupe vertices across face boundaries — a real watertight solid looks "non-manifold" to naive edge-count checks

- Root cause: `cq.Shape.tessellate(tol)` concatenates each FACE's own
  local `BRepMesh_IncrementalMesh` triangulation into one global
  (vertices, triangles) pair WITHOUT merging coincident vertices at
  shared face boundaries — two adjacent faces' triangulations each get
  their OWN vertex indices for the same 3D point on their shared edge. A
  naive "every edge (by vertex-index pair) must be shared by exactly 2
  triangles" manifold check therefore sees every shared-face-boundary
  edge as two DIFFERENT edges, each used only once, and reports a
  false non-manifold failure — even on a solid P4's own gate already
  proves watertight (found on te_half.yaml's `wing` body, P9 gate
  development, `tests/gates/test_p09_export.py`).
- Workaround: snap-merge tessellation vertices by rounded position
  (round to 1e-4mm — tighter than `TESSELLATION_TOLERANCE_MM` so
  genuinely distinct nearby vertices never wrongly merge, loose enough to
  catch the exactly/near-coincident ones OCC's per-face tessellation
  produces at a shared edge) BEFORE building the edge-adjacency map. See
  `test_p09_export.py::_is_manifold_tessellation`.
- Phase found: p09 (export gate, STL manifold-per-body check).

## BRepExtrema_DistShapeShape between two full lofted solids is intractable — proximity-cull to face subsets first

- Root cause: min-distance between two complete lofted wing bodies
  (hundreds of narrow ruled faces each, from 199-point section wires) at
  141 sweep angles blew an entire 10-hour pytest budget mid-sweep (P8
  gate, `test_clearance_floor_and_monotonic_trend`, 36,312s on the one
  test). The extrema search scales with the face-pair product; nothing
  about the per-call API misuse — the workload itself is the problem.
- Workaround: cull the static body to faces whose bbox comes within
  `KINEMATIC_PROXIMITY_CULL_MARGIN_MM` (25mm) of the moving body's
  rotation-swept bbox before ANY distance call
  (`kinematics.proximity_face_subsets` + `sweep_min_distance`). Sound for
  a floor assertion at any floor < margin: a culled face can never decide
  pass/fail (see the constant's derivation). Also drop per-angle boolean
  collision checks for skin-scale bodies — the swept-volume envelope test
  proves CONTINUOUS collision-freedom, strictly stronger than sampling.
- Phase found: p08 (`tests/gates/test_p08_kinematics.py`).

## Mac->remote rsync silently clobbers the remote's own gate artifacts/state.json

- Root cause: every code-push rsync this session used `--exclude`s for
  `.git`/`node_modules`/`.venv`/`artifacts/cache`/`frontend/node_modules`
  but NOT `artifacts/` itself — so pushing a code fix to the remote
  workspace also overwrote the remote's OWN `artifacts/state.json` and
  `artifacts/gates/*.json` (written by real gate runs ON the remote) with
  the Mac's stale local copies. Found empirically: P09's gate genuinely
  passed and recorded itself in the remote's state.json, then a later
  rsync (pushing the P8 kinematics.py fix) silently reverted
  `gates_passed` to the Mac's older list, losing the record — the P8 run
  that followed appended "p08" onto the STALE list, producing
  `[p00,p01,p02,p03,p04,p06,p08]` with p07 and p09 both missing despite
  p09 having actually passed.
- Workaround: gate artifacts flow ONE DIRECTION ONLY — remote-generated,
  pulled back to the Mac (git source of truth) after each real run, NEVER
  pushed from Mac to remote. Every code-push rsync must
  `--exclude='artifacts/'` (the whole tree, not just `artifacts/cache`).
  Recovered here by re-running the (cheap, ~7s) P09 gate for a fresh
  timestamped record rather than hand-patching the JSON.
- Phase found: p08/p09 (this session's autonomous verification cycles).
