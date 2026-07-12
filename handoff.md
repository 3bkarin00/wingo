# Handoff — 2026-07-13
## State
- Release/Phase: R1 / **P6 DONE** — `make gate PHASE=p06` passes
  (`artifacts/gates/p06.json`, `pass: true`); `make regress` confirms all
  6 prior gates (p00-p04, p06 — p05 retired, ADR-004/LE droop dropped)
  still green together. `artifacts/state.json`: `current_phase=p06`,
  `gates_passed` includes p06. Branch `phase/p06` (stacked on phase/p04)
  has every P6 commit, pushed to origin. P4 itself is still merge-ready
  (PR not yet opened — no `gh` CLI in this environment).
- P6 ("Sandwich internals + hardpoints", plan.md §8.7) construction,
  fully implemented and gate-verified this session:
  - **IML/sandwich-skin** (`backend/geometry/iml.py`): 3-layer panel
    (outer face / core / inner face) per wall, body-restricted, split
    upper/lower via camber-line parting prism (provisional — P15/P16's
    real parting curve supersedes it for tooling).
  - **False spar** (`backend/geometry/false_spar.py`): closes the device
    cut, `wall_prism ∩ hollow_iml_solid`.
  - **Cove-arc IML fidelity** (wing body): sandwich layers inside the
    device window follow the TRUE cove-cut boundary (was: original
    uncut airfoil — a real defect, fixed).
  - **Ramped drop-offs** (D11, `backend/geometry/iml.py`): core tapers to
    solid laminate at the wingtip edge. Only "edges" — hinge-land/joint/
    hardpoint ramping deferred (needs P7/P8/P11's own geometry first).
  - **Ribs** (`backend/geometry/ribs.py`): plane ∩ hollow-interior cavity,
    lightening holes via oversized-prism + `fuzzy_cut`, graceful fallback
    to solid slab when a hole doesn't fit. Device-window-edge ribs
    deferred (disconnected cross-section there).
  - **Spars trimmed to IML** (`backend/geometry/spar_trim.py`): thickens
    P3's zero-thickness ruled spar surfaces, trims to `hollow_interior`.
  - **Midsurfaces** (`backend/geometry/midsurface.py` + byproducts of
    ribs.py/reference.py): one shell per wall (D15), skin midsurface is
    clean-span only (no ramp/cove-fidelity correction — deferred).
  - **P6 gate** (`tests/gates/test_p06_sandwich.py`): battery is
    `te_half.yaml` only (cost-driven — a full build is ~45-90 real
    minutes even with the geometry cache warm; every module was ALSO
    independently stress-tested against `high_taper.yaml`, an extreme
    10:1-taper/mirror:true/single-ply-thin config, during development).
  - Every construction piece has its own docs/r0_findings/p06.md
    addendum with the real-kernel verification trail — several hit real,
    non-obvious OCC fragility (kernel-tolerance-adjacent floors, loft
    topology mismatches, raw-section-wire fragility, F4-style tangent
    boundaries) that took multiple rounds of empirical iteration to
    resolve; read the addenda before touching this code, not just this
    file.
## Next single action
- Start P7 — Hinges (generated mode), plan.md §9: "all hinge holes
  coaxial with their axis within 0.05mm, measured on the generated
  geometry; lug/tang clearance to moving body ≥ configured fit gap."
  `config.hinges` schema fields already exist (`mode: generated|cots`,
  `count`); P3 already builds the hinge AXIS (`reference.build_hinge_axes`)
  but not hinge hardware/holes. This is also what unblocks the
  hinge-land ramping (D11) and hardpoint-count-vs-P6-gate work that was
  deferred this phase. Branch `phase/p07` (stacked on `phase/p06`, not
  yet created) — create it before starting new construction work, per
  the project's per-phase branching convention (phase/p04 → phase/p06 →
  phase/p07).
## Blockers / open questions
- None technical. SSH push works; PRs merged by user in UI (no `gh` CLI).
- wingo.coder's workspace agent drops its apt-installed native libs
  (libGL etc.) across a restart — hit this MULTIPLE times this session,
  recovered every time via `docs/known_issues.md`'s documented workaround
  (`sudo apt-get update && sudo apt-get install -y libgl1 libglu1-mesa
  libxrender1 libxext6 libxcursor1 libxinerama1 libxft2 libxrandr2
  libxi6`). Not a code problem — check this first if cadquery import
  fails with `libGL.so.1` missing. Also: `docker compose` services
  (postgres/redis) can be fully stopped/removed across a workspace
  restart too — `make up` before any gate run that needs DB writes
  (`pytest_sessionfinish`'s `GateResultRow` insert) if `docker compose ps`
  comes back empty.
## Deferred scope (explicit, not forgotten)
- LE droop is DROPPED (ADR-004), not deferred — don't resurrect without a
  new explicit product decision.
- Within P6 (all tracked with their own docs/r0_findings/p06.md note,
  not just here): control-surface nose sandwich fidelity (mirror
  construction to the wing-cove fix, offset INWARD from a radius-R arc;
  CS sandwich isn't wired into any export/gate path at all yet);
  hinge-land/joint/hardpoint-specific ramping (need P7/P8/P11's
  geometry); device-window-edge ribs (disconnected cross-section);
  rib/spar mutual notching (both built as independent solids this phase,
  physically must cross — real aircraft ribs are notched, this phase's
  gate explicitly excludes rib-vs-spar from its interference check
  rather than pretending they don't touch); skin-midsurface ramp/cove-
  fidelity correction; P6 gate battery beyond `te_half.yaml`.
## Do not touch
- P0–P4, P6 gates are frozen contracts (docs/gate_changes.md: one entry,
  for the P3 le_droop-reference removal — P6 itself has no gate_changes.md
  entry since it was authored fresh this session, not modified after the
  fact).
- `backend/geometry/iml.py`'s offset chain is the full-value triple
  `face_mm, core_mm, face_mm` — a sandwich panel is 3 layers PER WALL, and
  the frozen P0 `stack_mm = core + 2*face` is the PER-WALL panel thickness,
  NOT a two-wall budget. Total local consumption is `2*stack_mm`; where a
  section is thinner the innermost offsets SELF-CLIP (`kind="intersection"`)
  and walls merge into solid laminate — R0-verified safe and now also
  P6-gate-verified (`test_iml_min_wall_audit`'s solid-laminate floor of
  `2*face_mm`). Read r0_findings/p06.md (superseded marker + addenda)
  before touching this chain.
- `iml.py` still does NOT build CS-nose sandwich fidelity — do not call
  `build_sandwich_body` on `control_surface` and trust the result inside
  an enabled device's spanwise window.
- Device cove/nose = SINGLE per-station axis-centered arc (ADR-003); hinge
  axis height is DERIVED (`derive_hinge_axis`, reference.py). Config-time
  validation (`NOSE_TANGENCY_MAX_DEG=2.0°`) REJECTS configs that can't keep
  Ru≈Rl close enough — intentional fail-fast.
- Gate tests build geometry through `tests/gates/geometry_cache.py`. Read
  `artifacts/gates/p04_timings.json` / `p06_timings.json` or
  `--durations=20` to diagnose a slow config; never re-run a full
  geometry-build gate as a stopwatch. P6's booleans varied run-to-run by
  up to ~2x on this workspace with IDENTICAL code+config this session
  (`core_ring_s`: 653s → 1209s → 1721s → 1697s → 1710s across five runs) —
  a wall-clock delta between two runs is noise unless the per-stage
  `timings_s` breakdown disagrees qualitatively, not just in magnitude.
- `SandwichLofts`'s three IML fields and `false_spar.build_false_spar`'s
  `hollow_iml_solid` parameter are typed `cq.Shape` (not `cq.Solid`) since
  the cove-fidelity cut can return a compound — don't narrow these back.
- `reference.get_canonical_points_at_xc` and `iml.offset_wire` are PUBLIC
  now (were `_get_canonical_points_at_xc`/`_offset_wire`) — spar_trim.py
  and midsurface.py reuse them. Don't re-privatize without checking those
  call sites.
- P6's gate (`test_p06_sandwich.py`) EXCLUDES specific body pairs from its
  pairwise-interference check (rib-vs-spar, false_spar-vs-rib/spar) —
  this is deliberate (structural crossing + documented bond flange, see
  the test's own docstring), not a weakened check: rib-vs-rib and
  spar-vs-spar are still checked and would fail the gate if they ever
  overlapped.
