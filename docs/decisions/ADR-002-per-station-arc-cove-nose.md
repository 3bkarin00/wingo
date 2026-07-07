# ADR-002 — Per-station axis-centered arcs replace the deliberate-clearance-angle cylinder mechanism

**Status**: Accepted (P4, folded into plan.md §8.5 refinement).

## Context

P4-v1 built the control-surface nose and wing cove as two coaxial cylinders
about the hinge axis: `nose_cyl` radius sized as a fraction of local
half-thickness (`TE_NOSE_RADIUS_FRACTION`, an ad-hoc heuristic), `cove_cyl`
radius = `nose_cyl + gap_mm`. This conserved volume exactly (OML partitions
into wing/CS/gap by construction) and avoided F4 (distinct radii ⇒ never
tangent), but had two real problems:

1. **No real tangency condition.** The nose cylinder's radius was a fraction
   of thickness, not derived from where the skin actually is — nothing made
   the nose surface tangent to the OML skin, so at a real deflection angle
   the swept nose could clip the skin or leave an oversized gap depending on
   local curvature.
2. **Brittle at a requested clearance.** At `gap_mm=5mm` on a thin station,
   `nose_cyl` didn't fit inside the local half-thickness — the CS split into
   2 disjoint bodies instead of 1 (nose region no longer overlapped the aft
   box), failing `test_exactly_two_watertight_bodies` outright.

## Decision

Replace the uniform-gap cylinder pair with a **per-station construction** in
planes perpendicular to the (possibly tilted) hinge axis:

- At each station, `C` = hinge-axis point in that plane. `Pu`/`Pl` = the
  *normal feet* of `C` on the upper/lower OML skin (nearest points). The
  nearest-point vector `C→P` is always ⟂ the skin's local tangent — this is
  a property of nearest-point projection, not a solved or iterated
  constraint — so a circular arc centered on `C` through `P` is tangent to
  the skin at `P` by construction.
- **CS nose**: if `|Ru − Rl| ≤ NOSE_RADII_MATCH_MM`, one arc at the mean
  radius with a short blend onto the exact feet; otherwise two true-radius
  arcs joined by a G1 Hermite blend crossing the chord line forward of `C`.
  Either way the nose is entirely axis-centered arcs (plus short blends), so
  its radius is constant under rotation about the axis — the swept envelope
  at any deflection angle equals the profile itself.
- **Wing cove**: a single concave arc at the *same* `C`, radius
  `max(Ru, Rl) + COVE_CLEARANCE_MM` (5.0mm, `backend/tolerances.py`) — never
  tangent to the nose (F4), and — because both nose and cove are centered on
  the same axis point at every station — the radial offset between them is
  invariant under rotation about the axis. `test_cove_clearance_at_rest_and_
  deflected` verifies this explicitly at 0° AND at `max_deflection_deg`, not
  just at rest.
- Per-station profiles are lofted (polygon wires + `ruled=True`, matching the
  OML's own P2 construction) into nose/cove REGION solids, which then play
  the exact role the P4-v1 cylinders played in the boolean split: `CS = OML
  ∩ (nose_region ∪ aft_box_cs)`, `wing = OML − cove_region − aft_box_wing`.
  The volume-conserving boolean algebra is unchanged from P4-v1 — only what
  the "cylinder" actually IS changed.

`COVE_CLEARANCE_MM = 5.0` **replaces** `gap_mm` as the mechanism that
determines nose-to-cove radial clearance. `gap_mm` still exists and still
matters — it's the *spanwise* inset of the CS body from the wing at each end
of the device span, a separate, orthogonal clearance dimension — but it no
longer has any role in sizing the nose/cove radial gap the way P4-v1's
`R_cove = R_nose + gap_mm` did.

## Consequences

- Retired: `TE_NOSE_RADIUS_FRACTION` and the other v1 cylinder-sizing
  tolerances (no longer meaningful once the nose radius comes from real
  normal-foot geometry, not a thickness fraction).
- Added tolerances (`backend/tolerances.py`, each with a derivation
  comment): `COVE_CLEARANCE_MM`, `NOSE_RADII_MATCH_MM`,
  `NOSE_TANGENCY_ANGLE_TOL_DEG`, `COVE_CLEARANCE_TOL_MM`,
  `COVE_LEAD_IN_FILLET_MM`, `NOSE_AFT_OVERLAP_MM` (the last one a P4-v2-only
  construction fix: the nose polygon must reach aft past the hinge far
  enough to overlap `aft_box_cs`, or `.fuse()` leaves 2 disjoint bodies —
  same failure MODE as v1's problem #2 above, different cause, fixed at its
  actual source this time instead of by choosing a smaller `gap_mm`).
- Added gates (`tests/gates/test_p04_te_cut.py`): `test_nose_tangency`
  (normal-foot vector ⟂ skin tangent, ≥20 stations), `test_nose_axis_
  centered` (sealed-region points on the REAL built CS solid, sampled via an
  actual OCC section, sit at the constructed per-station radius — not a
  re-evaluation of the construction formula, which would trivially
  self-satisfy), `test_cove_clearance_at_rest_and_deflected` (min radial gap
  == `COVE_CLEARANCE_MM` at 0° and at `max_deflection_deg`, sampled only on
  vertices axially interior to the CS's spanwise extent so the pre-existing
  `gap_mm` spanwise clearance can't be mistaken for the radial one),
  `test_two_arc_nose_branch_no_duplicate_points` (pure-numpy construction
  check for the two-arc/Hermite branch, not currently exercised by either
  device config but latent — see changelog.md 2026-07-07).
- `test_exactly_two_watertight_bodies`, `test_volume_conservation`,
  `test_no_shards`, `test_no_interbody_tangency` (F3/F4/§9 P4 pass criteria)
  are unchanged in intent — same boolean algebra, now verified against the
  per-station construction's actual output.
- P5 (LE droop) reuses this identical construction (same tolerances, same
  per-station machinery in `cove_profile.py`) unless a config explicitly
  overrides the clearance.
