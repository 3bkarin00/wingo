# Handoff — 2026-07-11
## State
- Release/Phase: R1 / P4 DONE + merged-ready (phase/p04 pushed, PR still
  needs opening manually — no `gh` CLI in this environment). LE droop
  dropped from scope entirely (ADR-004) before P5 started. P5's phase slot
  is retired/unused; branch `phase/p06` created (stacked on phase/p04, not
  yet merged) for P6 "Sandwich internals + hardpoints" (plan.md §8.7).
- P6 progress (NOT gated yet — `make gate PHASE=p06` has not been attempted,
  no `artifacts/gates/p06.json` exists): the IML/sandwich-skin construction
  for the CLEAN SPAN (away from the TE device window) is implemented
  (`backend/geometry/iml.py`) as the corrected THREE-layer panel — outer
  face sheet / core / inner face sheet per wall (product review caught the
  first version missing the inner face sheet; a second review earlier caught
  the core band not being body-restricted). All three rings are
  body-restricted and split into upper/lower shells via a camber-line
  parting prism (provisional parting — P15/P16's real max-half-breadth
  parting curve supersedes it for tooling).
- False-spar closing wall (`backend/geometry/false_spar.py`) implemented
  and verified against the real kernel on `tests/configs/devices/te_half.yaml`
  (2026-07-11, on wingo.coder): `wall_prism ∩ hollow_iml_solid`, no shards,
  watertight, spans the device window, CS clearance 5.50mm ≥
  `COVE_CLEARANCE_MM`. New-code cost is cheap (12.6s of the run's ~35min —
  the rest is the pre-existing sandwich-shell booleans, `core_ring_s=653s`
  / `face_inner_ring_s=706s`, consistent with the documented variance).
  Wired into `scripts/export_viewer_data.py` (`vol["false_spar"]`,
  `tess["wing_false_spar"]`) and `tools/viewer/app.js` (new WIP layer,
  lime green `FALSE_SPAR`). New tolerance `FALSE_SPAR_COVE_STANDOFF_MM`
  in `backend/tolerances.py`. Only tested on `te_half`; NOT yet run against
  the aft-hinge configs (`te_half_twisted_moderate`, `devices_full`,
  `high_taper`) where the KNOWN DESIGN TENSION note below applies.
  Verification asserts run inside the viewer-export path itself on every
  export: zero shards, watertight, upper+lower exactly partitions each of
  the 3 rings, false-spar spans + CS clearance. See docs/r0_findings/p06.md
  (SUPERSEDED marker + both addenda) for the full derivation history.
## Next single action
- Continue P6: the nose/cove-arc region sandwich fidelity is the next
  concrete piece (currently `iml.py` offsets the ORIGINAL uncut airfoil
  sections everywhere, which is WRONG near the hinge — the wing/CS's actual
  boundary there is `cove_profile.py`'s arc, not the airfoil skin; `iml.py`'s
  own module docstring states this limitation explicitly). Before that,
  optionally run the false-spar export against the 3 aft-hinge configs
  (`te_half_twisted_moderate`, `devices_full`, `high_taper` — ~30-40min each
  on wingo.coder) to confirm the KNOWN DESIGN TENSION note in
  `false_spar.py` (wall landing near/straddling the rear spar plane) doesn't
  actually break the CS-clearance or watertight asserts there. After the
  cove-arc fix: ramped drop-offs (`ramp_ratio`, station-varying `core_mm` —
  same offset machinery, no new construction path needed per
  r0_findings/p06.md), ribs (plane ∩ hollow volume, lightening-hole cutouts
  as 2D face ops before thickening), spars trimmed to IML (thicken P3's
  existing ruled spar surfaces), midsurface faces (built alongside solids,
  not extracted later), then finally `tests/gates/test_p06_sandwich.py` +
  `make gate PHASE=p06`.
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
- Within P6, explicitly NOT done yet: device-region (nose/cove-arc) sandwich
  fidelity (false spar itself is DONE — see State above); ramped drop-offs;
  ribs; spar-trim-to-IML; midsurfaces; the real P6 gate test file and
  `make gate PHASE=p06` run.
## Do not touch
- P0–P4 gates are frozen contracts (docs/gate_changes.md: one entry, for
  the P3 le_droop-reference removal).
- `backend/geometry/iml.py`'s offset chain is the full-value triple
  `face_mm, core_mm, face_mm` — a sandwich panel is 3 layers PER WALL, and
  the frozen P0 `stack_mm = core + 2*face` is the PER-WALL panel thickness
  (same reading the P3 hinge-margin gate uses), NOT a two-wall budget. The
  first implementation got this wrong (offsets `face_mm, core_mm/2`, no
  inner face sheet) by treating stack_mm as total consumption — do not
  regress to that. Total local consumption is `2*stack_mm`; where a section
  is thinner (aft ~10% chord at the tip on te_half_twisted_moderate,
  devices_full, high_taper) the innermost offsets SELF-CLIP
  (kind="intersection") and walls merge into solid laminate — R0-verified
  safe (probe_ocp_offset_3layer.py: single valid closed wires, valid lofts,
  exact conservation), accepted until ramped drop-offs (D11)/P6 gate IML
  audit. Read r0_findings/p06.md (superseded marker + addenda) first.
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
