# Handoff — 2026-07-08
## State
- Release/Phase: R1 / P4 DONE and merged-ready (phase/p04 pushed). LE droop
  dropped from scope entirely (ADR-004) before P5 started — product
  decision, not a technical finding. P5's phase slot is retired/unused;
  P6 onward keep their original numbers (no renumbering).
- Last green gate: p04 (artifacts/gates/p04.json, 25 tests). `make regress`
  (p00-p04) re-verified green on wingo.coder AFTER the LE-droop removal
  (schema field + validators + reference.py + one frozen P3 test edit,
  logged in docs/gate_changes.md) — nothing broke.
## Next single action
- Branch phase/p06 off main (once phase/p04's PR is merged — push already
  done, PR still needs opening in the GitHub UI, no `gh` CLI in this
  environment). Start P6 "Sandwich internals + hardpoints" (plan.md §8.7,
  §9 P6): IML by 2D per-station offset + second loft + subtract (NEVER OCC
  shell/thicken, F1); core volume with ramped drop-offs (`ramp_ratio`) at
  edges/hinge lands/joints/hardpoints; ribs as plane ∩ inner volume with
  cutouts/holes as 2D face ops pre-thickening; spars trimmed to IML; false
  spars close the TE device cut faces; midsurface faces constructed
  alongside the solids, not extracted later. Gate: pairwise boolean
  interference = 0 across ALL bodies; every auto hardpoint has core
  ramp-out; IML audit (min wall >= face-sheet stack, sampled); every rib
  watertight after holes/cutouts; midsurface face count matches structural
  body count.
## Blockers / open questions
- None. SSH push works; PRs merged by user in UI (no `gh` CLI available in
  this environment — PR creation/update for phase/p04 still needs doing
  manually in the GitHub web UI when ready).
## Deferred scope (explicit, not forgotten)
- CS internal structure (LE spar/web carrying hinge tangs, CS-body end
  ribs, sandwich skin with core ramp-out, TE closeout wedge, optional
  counterbalance mass-rod channel, wing-side Ansys reinforcement named
  selections) maps onto P6 ("Sandwich internals + hardpoints", generic for
  every device — build it there, not bespoke), P7 ("Hinges"), R2 ("Ansys
  export package").
- LE droop is NOT deferred — it's dropped (ADR-004). Don't resurrect
  `le_droop`/P5 without a new explicit product decision; if one comes, it
  re-adds the schema field, the two removed P0 validators/error codes, and
  a new `le_cut.py` (the mirrored-`a`-direction construction sketched
  before the drop — negate the chordwise-aft unit vector so cove_profile.py's
  existing arc/loft machinery bulges the nose toward the wing correctly on
  either edge — is still the right approach if this comes back).
## Do not touch
- P0–P4 gates are frozen contracts (docs/gate_changes.md for changes; one
  entry there now, for the P3 le_droop-reference removal).
- OML = polygon wires + ruled=True (r0_findings/p02.md). Hinge-axis margin
  uses distance-to-SHELL (r0_findings/p03.md).
- Device cove/nose = SINGLE per-station axis-centered arc (ADR-003): nose
  is one arc at R=(Ru+Rl)/2, extended angularly beyond Pu/Pl by
  max_deflection+OVERLAP_MARGIN_DEG (anti-unporting). The hinge axis HEIGHT
  is DERIVED (backend/geometry/reference.py `derive_hinge_axis`,
  least-squares fit to the true equidistant-from-skin point at 24
  stations). Config-time validation (NOSE_TANGENCY_MAX_DEG=2.0°) REJECTS a
  config whose twist/hinge_xc combination can't keep Ru≈Rl close enough —
  intentional fail-fast, not a bug if a new config gets rejected.
- Gate tests build geometry through `tests/gates/geometry_cache.py` (lazy,
  indirect-parametrized fixtures) — a `-k <stem>` run must only ever build
  that one config. Read `artifacts/gates/p04_timings.json` or
  `--durations=20` to diagnose a slow config; never re-run a full
  geometry-build gate as a stopwatch.
- `tests/configs/devices/te_half_twisted.yaml` is a DELIBERATE negative
  test case (-8° tip twist, correctly rejected by validation) — not part
  of the "must successfully build" battery.
- `Config` has no `le_droop` field anymore (ADR-004) — `_enabled_devices()`
  (backend/schema/validators.py) only ever returns `te_surface`;
  `ref.hinge_axes` (backend/geometry/reference.py) is still a dict keyed by
  device name (currently only ever `"te"`), kept that shape deliberately
  rather than collapsing to a single edge.
