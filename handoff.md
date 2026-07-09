# Handoff — 2026-07-09
## State
- Release/Phase: R1 / P4 DONE + merged-ready (phase/p04 pushed, PR still
  needs opening manually — no `gh` CLI in this environment). LE droop
  dropped from scope entirely (ADR-004) before P5 started. P5's phase slot
  is retired/unused; branch `phase/p06` created (stacked on phase/p04, not
  yet merged) for P6 "Sandwich internals + hardpoints" (plan.md §8.7).
- P6 progress (NOT gated yet — `make gate PHASE=p06` has not been attempted,
  no `artifacts/gates/p06.json` exists): the IML/sandwich-skin construction
  for the CLEAN SPAN (away from the TE device window) is implemented
  (`backend/geometry/iml.py`) and verified against the real kernel on both
  `te_half.yaml` and `te_half_twisted_moderate.yaml`. All layers are
  body-restricted (a first version's core band wasn't — it sailed uncut
  through the CS pocket, caught by product review in the dev viewer), and
  skins are delivered SPLIT into upper/lower shells via a camber-line
  parting prism (provisional parting — P15/P16's real max-half-breadth
  parting curve supersedes it for tooling). Verification asserts run inside
  the viewer-export path itself on every export: zero shards, watertight,
  upper+lower exactly partitions each ring. See docs/r0_findings/p06.md
  (incl. addendum) for the full derivation.
## Next single action
- Continue P6: the device-region follow-on is the next concrete piece —
  build the false-spar closing wall at the TE cut face + make the
  sandwich construction correct in the nose/cove-arc region (currently
  `iml.py` offsets the ORIGINAL uncut airfoil sections everywhere, which is
  WRONG near the hinge — the wing/CS's actual boundary there is
  `cove_profile.py`'s arc, not the airfoil skin; `iml.py`'s own module
  docstring states this limitation explicitly). After that: ramped
  drop-offs (`ramp_ratio`, station-varying `core_mm` — same offset
  machinery, no new construction path needed per r0_findings/p06.md), ribs
  (plane ∩ hollow volume, lightening-hole cutouts as 2D face ops before
  thickening), spars trimmed to IML (thicken P3's existing ruled spar
  surfaces), midsurface faces (built alongside solids, not extracted
  later), then finally `tests/gates/test_p06_sandwich.py` + `make gate
  PHASE=p06`.
## Blockers / open questions
- None technical. SSH push works; PRs merged by user in UI (no `gh` CLI).
- wingo.coder's workspace agent can drop connection and/or lose the
  apt-installed native libs (libGL etc.) across a restart — hit this
  session, recovered via `docs/known_issues.md`'s existing documented
  workaround (`sudo apt-get update && sudo apt-get install -y libgl1
  libglu1-mesa libxrender1 libxext6 libxcursor1 libxinerama1 libxft2
  libxrandr2 libxi6`). Not a code problem — check this first if cadquery
  import fails with `libGL.so.1` missing.
## Deferred scope (explicit, not forgotten)
- LE droop is DROPPED (ADR-004), not deferred — don't resurrect without a
  new explicit product decision.
- Within P6, explicitly NOT done yet (tracked in the plan approved this
  session, `/Users/salah/.claude/plans/eager-stargazing-lightning.md`, and
  above): device-region (nose/cove-arc) sandwich fidelity + false spar;
  ramped drop-offs; ribs; spar-trim-to-IML; midsurfaces; the real P6 gate
  test file and `make gate PHASE=p06` run.
## Do not touch
- P0–P4 gates are frozen contracts (docs/gate_changes.md: one entry, for
  the P3 le_droop-reference removal).
- `backend/geometry/iml.py`'s offset sequence is NOT arbitrary — it's the
  ONLY one consistent with the FROZEN P0 `stack_mm = core + 2*face`
  formula. R0-derived (docs/r0_findings/p06.md): a SINGLE whole-loop
  `cq.Wire.offset2D(-d)` pass shrinks local wall thickness by `2d`, not `d`
  (empirically confirmed, 2.00x). So: `face_sheet_IML =
  outer.offset2D(-face_mm)` [consumes `2*face_mm`], `hollow_IML =
  face_sheet_IML.offset2D(-core_mm/2)` [consumes `2*(core_mm/2) =
  core_mm`] — total `2*face_mm + core_mm == stack_mm` exactly. A naive
  "offset by face, then by core" (not core/2) would consume MORE than
  `stack_mm` and silently break the tightest-margin frozen config
  (`te_half_twisted_moderate.yaml`) even though it passes P0 validation.
  Never re-derive this from scratch — read r0_findings/p06.md first.
- `iml.py` is CLEAN-SPAN ONLY (module docstring states this) — do not call
  `build_sandwich_body` and trust the result inside an enabled device's
  spanwise window until the device-region follow-on lands.
- Device cove/nose = SINGLE per-station axis-centered arc (ADR-003); hinge
  axis height is DERIVED (`derive_hinge_axis`, reference.py). Config-time
  validation (`NOSE_TANGENCY_MAX_DEG=2.0°`) REJECTS configs that can't keep
  Ru≈Rl close enough — intentional fail-fast.
- Gate tests build geometry through `tests/gates/geometry_cache.py` (lazy,
  indirect-parametrized fixtures). Read `artifacts/gates/p04_timings.json`
  or `--durations=20` to diagnose a slow config; never re-run a full
  geometry-build gate as a stopwatch. The P6 booleans are genuinely slow
  (face-sheet cut alone 226-292s measured) AND their wall-time varies
  ~4.6x run-to-run on the workspace with identical inputs
  (docs/known_issues.md) — a wall-clock delta between two runs is noise
  unless the per-stage `timings_s` breakdown agrees. `build_sandwich_body`'s
  `include_hollow_interior=False` exists because the hollow-interior boolean
  is the single most expensive one (~370s) and the viewer doesn't need it;
  the real P6 pipeline ALWAYS computes it (ribs/spars live inside it).
- The upper/lower skin split's camber pairing (`_camber_polyline`) relies on
  resample.py's contract: odd point count, upper/lower on the SAME cosine
  x-grid, shared LE, canonical TE→upper→LE→lower→TE order. If resampling
  ever changes, that helper breaks silently — the export-path partition
  assert is what catches it.
