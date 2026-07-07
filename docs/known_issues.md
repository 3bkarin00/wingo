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
