# Handoff — 2026-07-11
## State
- Release/Phase: R1 / P4 DONE + merged-ready (phase/p04 pushed, PR still
  needs opening manually — no `gh` CLI in this environment). LE droop
  dropped from scope entirely (ADR-004) before P5 started. P5's phase slot
  is retired/unused; branch `phase/p06` created (stacked on phase/p04, not
  yet merged) for P6 "Sandwich internals + hardpoints" (plan.md §8.7).
- P6 progress (NOT gated yet — `make gate PHASE=p06` has not been attempted,
  no `artifacts/gates/p06.json` exists): the IML/sandwich-skin construction
  is implemented (`backend/geometry/iml.py`) as the corrected THREE-layer
  panel — outer face sheet / core / inner face sheet per wall. All three
  rings are body-restricted and split into upper/lower shells via a
  camber-line parting prism (provisional — P15/P16's real max-half-breadth
  parting curve supersedes it for tooling).
- False-spar closing wall (`backend/geometry/false_spar.py`) implemented:
  `wall_prism ∩ hollow_iml_solid`, standoff forward of the cove sweep, one
  skin-stack thick. Wired into `scripts/export_viewer_data.py`
  (`vol["false_spar"]`, `tess["wing_false_spar"]`) and `tools/viewer/app.js`
  (WIP layer, lime green `FALSE_SPAR`). New tolerance
  `FALSE_SPAR_COVE_STANDOFF_MM` in `backend/tolerances.py`.
- Wing-side cove-arc IML fidelity implemented: `iml.build_sandwich_lofts`
  now subtracts a cove-following wedge (`te_cut.build_cove_offset_region`,
  new; `cove_profile.build_cove_arc_points` gained `extra_radius_mm`) from
  each of the three offset lofts when te_surface is enabled, so the
  sandwich layers inside the device window follow the TRUE cove-cut
  boundary instead of the original uncut airfoil. Resolves iml.py's old
  DELIBERATE SCOPE LIMIT for the WING body (CS nose sandwich is still
  unbuilt — see Deferred below).
- **Both features verified together against the real kernel**
  (`tests/configs/devices/te_half.yaml`, wingo.coder, 2026-07-11): sandwich
  shells 3-ring-partitioned/watertight/shard-free (`cove_fidelity_s=93.9s`);
  false spar re-verified against the now-corrected cavity (vol
  31442→10237mm³, CS clearance 5.50→7.42mm — smaller, better-clearanced,
  as expected once the cavity stops at the true cove boundary). Only
  `te_half` has been run — NOT yet the 3 aft-hinge configs
  (`te_half_twisted_moderate`, `devices_full`, `high_taper`) where
  false_spar.py's KNOWN DESIGN TENSION note applies. `tools/viewer/dist/viewer.html`
  + `artifacts/viewer_data.json` regenerated from this run for visual
  inspection (both gitignored, not committed — regenerate per
  `tools/viewer/README.md` if needed again).
  See docs/r0_findings/p06.md (SUPERSEDED marker + 4 addenda, newest is
  "cove-arc IML fidelity") for the full derivation history.
## Next single action
- Continue P6: ramped drop-offs (`ramp_ratio`, station-varying `core_mm` —
  same offset machinery, no new construction path needed per
  r0_findings/p06.md) — the next construction piece per plan.md §8.7's
  order. Optionally first run the false-spar + cove-fidelity export against
  the 3 aft-hinge configs (~30-50min each on wingo.coder now, slower than
  before per the cove_fidelity_s addition) to confirm the KNOWN DESIGN
  TENSION note in `false_spar.py` doesn't break there. After ramped
  drop-offs: ribs (plane ∩ hollow volume, lightening-hole cutouts as 2D
  face ops before thickening), spars trimmed to IML (thicken P3's existing
  ruled spar surfaces), midsurface faces (built alongside solids, not
  extracted later), then finally `tests/gates/test_p06_sandwich.py` +
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
- Within P6, explicitly NOT done yet: control-surface nose sandwich
  fidelity (mirror construction to the wing-cove fix above — offset INWARD
  from a radius-R arc rather than outward from R+COVE_CLEARANCE_MM; CS
  sandwich shells aren't wired into any export/gate path yet at all);
  ramped drop-offs; ribs; spar-trim-to-IML; midsurfaces; the real P6 gate
  test file and `make gate PHASE=p06` run.
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
- `iml.py` still does NOT build CS-nose sandwich fidelity — do not call
  `build_sandwich_body` on `control_surface` and trust the result inside an
  enabled device's spanwise window (the wing-side call is now fixed; the CS
  side is not, and isn't wired into the export path to begin with).
- Device cove/nose = SINGLE per-station axis-centered arc (ADR-003); hinge
  axis height is DERIVED (`derive_hinge_axis`, reference.py). Config-time
  validation (`NOSE_TANGENCY_MAX_DEG=2.0°`) REJECTS configs that can't keep
  Ru≈Rl close enough — intentional fail-fast.
- Gate tests build geometry through `tests/gates/geometry_cache.py` (lazy,
  indirect-parametrized fixtures). Read `artifacts/gates/p04_timings.json`
  or `--durations=20` to diagnose a slow config; never re-run a full
  geometry-build gate as a stopwatch. The P6 booleans are genuinely slow
  AND their wall-time varies significantly run-to-run on the workspace with
  identical inputs (docs/known_issues.md) — e.g. `core_ring_s` measured
  653s then 1209s across two back-to-back te_half runs this session, same
  code+config — a wall-clock delta between two runs is noise unless the
  per-stage `timings_s` breakdown disagrees qualitatively (shape, not just
  magnitude). `build_sandwich_body`'s `include_hollow_interior=False`
  exists because the hollow-interior boolean is among the most expensive
  operations (~370s+) and the viewer doesn't need it; the real P6 pipeline
  ALWAYS computes it (ribs/spars live inside it).
- The upper/lower skin split's camber pairing (`_camber_polyline`) relies on
  resample.py's contract: odd point count, upper/lower on the SAME cosine
  x-grid, shared LE, canonical TE→upper→LE→lower→TE order. If resampling
  ever changes, that helper breaks silently — the export-path partition
  assert is what catches it.
- `SandwichLofts`'s three IML fields are typed `cq.Shape` (not `cq.Solid`)
  since the cove-fidelity cut can return a compound — same for
  `false_spar.build_false_spar`'s `hollow_iml_solid` parameter. Don't
  narrow these back to `cq.Solid`.
