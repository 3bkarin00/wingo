# ADR-003 — Single-arc nose + derived hinge-axis height replaces the two-arc/Hermite-blend construction

**Status**: Accepted (P4, refines ADR-002).

## Context

ADR-002's per-station arc construction had a fallback branch: if a station's
upper/lower normal-foot radii (Ru, Rl) differed by more than
`NOSE_RADII_MATCH_MM` (1.0mm), the nose used two true-radius arcs joined by
a G1 Hermite blend instead of one shared-radius arc. On a wing with any
spanwise twist, this branch fired at nearly every nose station (not just
the ones near the tip, or the ones with the largest twist — see the
diagnosis below) and produced a visibly **lumpy** nose: G1 continuity only
matches tangent *direction* at the arc/blend junction, not tangent
*magnitude* (curvature), so the profile shows a real curvature
discontinuity there. Confirmed geometric, not a rendering artifact, via two
independent checks (docs/r0_findings/p04.md):

- Re-tessellating the same nose loft at 0.5mm vs. 0.05mm (10x finer)
  produced the *identical* vertex/triangle count — the ruled-loft surface
  has no smooth curvature for a finer tolerance to resolve, so any visible
  lumpiness has to be in the construction, not the tessellation.
- A discrete curvature-angle proxy along the raw construction points showed
  a real spike (std 1.94°, worst point 2.6x the local mean) on a twisted
  config, vs. a clean, near-constant profile (std 0.11°, 1.1x) on an
  untwisted one.

**Root cause was one level deeper than "twist causes asymmetry" though.**
`backend/geometry/reference.py`'s `build_hinge_axes` placed the hinge axis
height at the *arithmetic mean* of the upper/lower skin z-height at
`hinge_xc`, sampled at only the two span endpoints, connected by a straight
line. That mean is not the same point as the one *equidistant* from the
upper/lower skin curves (nearest-point distance) except where the skin is
locally flat — for a cambered airfoil they differ even at zero twist
(measured: te_half showed Ru-Rl residual ~0.09mm from this alone), and
under twist the mismatch grows because only two points define the whole
axis. This is why the two-arc branch fired even at fairly small twist
values, and why the effect didn't simply track twist magnitude.

## Decision

Two changes, together:

1. **Derived hinge-axis height** (`backend/geometry/reference.py`,
   `derive_hinge_axis`): `hinge_xc` still fixes the chordwise (X) position
   exactly as before. The vertical (Z) position is now DERIVED — sample the
   TRUE equidistant-from-skin height (found by bisection: the z on the
   `x=hinge_xc` line where nearest-distance-to-upper-surface equals
   nearest-distance-to-lower-surface) at `AXIS_HEIGHT_FIT_STATIONS` (24)
   points across the span, then fit a straight line through them by least
   squares (`docs/conventions.md` §5 requires the axis stay a perfectly
   straight 3D line; the true equidistant height is not itself linear in
   general, so least squares is the closest straight-line approximation,
   not a re-derivation of the exact curve). Residuals are always computed
   and reported (`test_axis_equidistant_residual`), never hidden.
2. **Single arc only** (`backend/geometry/cove_profile.py`,
   `build_nose_arc_points`): the two-arc branch and its Hermite blend are
   deleted entirely — no conditional branching on `|Ru-Rl|` at all. Every
   station's nose is one arc at `R = (Ru+Rl)/2`. Because the derived axis
   keeps Ru and Rl close (typically <0.03mm apart after the fit, vs. up to
   several mm before), this single arc is a faithful approximation
   everywhere it's valid — and where it *isn't* (too much camber/twist for
   a straight axis at a given `hinge_xc`), **config-time validation rejects
   the config outright** (`ConfigErrorCode.NOSE_TANGENCY_EXCEEDS_MAX`,
   raised from `te_cut.py`'s `_validate_nose_tangency`) rather than
   silently degrading the shape with a blend. The rejection message names
   the actionable fix: reduce twist, move `hinge_xc`, or shorten the
   control-surface span.

`NOSE_TANGENCY_MAX_DEG` (2.0°) gates this — calibrated from real
measurement, **not** the literal 0.5° suggested when this redesign was
scoped. At any realistic aft `hinge_xc` (~0.70-0.75, the only region a
typical rear spar leaves valid), the mean-radius tangency error scales
close to linearly with twist at ~1.7° per degree of tip twist
(`docs/r0_findings/p04.md`) — 0.5° would reject nearly every wing with any
nonzero twist at a realistic TE hinge position, not just pathological ones.
2.0° accommodates a real, measured 1° tip-twist config (1.70° residual,
~15% margin) while still rejecting the project's own extreme-twist edge
case. The metric itself (`mean_radius_tangency_err_deg`,
`cove_profile.py`) uses `arctan(|R-Ru|/Ru)`, not an `arccos`-based
formulation — `arccos` has an infinite derivative at ratio=1 and
over-reports even a ~0.001mm mismatch as several tenths of a degree
(measured directly while calibrating this ADR).

**Anti-unporting angular overlap** (design-practice addition, same change):
the nose arc no longer stops exactly at the tangent points Pu/Pl. It's
extended beyond each by `max_deflection_deg + OVERLAP_MARGIN_DEG` (4.0°),
so the curved nose still overlaps the fixed wing's cove lips at full
deflection and never rotates out of the cove ("unporting", exposing a bare
edge to airflow). The wing cove arc uses the identical extended range.
Verified on the real built solid (`test_no_unporting`): rotating the arc's
extended endpoint by ±max_deflection about the real hinge axis and
re-measuring its angle empirically confirmed exactly `OVERLAP_MARGIN_DEG`
of margin remains at the tightest case — matching the construction formula
exactly, not just algebraically.

## Consequences

- Retired: `NOSE_RADII_MATCH_MM` (no branch to gate anymore),
  `NOSE_TANGENCY_ANGLE_TOL_DEG` (replaced by `NOSE_TANGENCY_MAX_DEG`, a
  different metric calibrated for a different purpose — the numeric
  coincidence with the old value's 2.0° is exactly that, a coincidence).
- Added tolerances: `NOSE_TANGENCY_MAX_DEG` (2.0°),
  `OVERLAP_MARGIN_DEG` (4.0°).
- Added schema field: `DeviceWindow.overlap_margin_deg` (optional
  per-config override of `OVERLAP_MARGIN_DEG`, shared by `te_surface` and
  `le_droop`).
- Added error code: `ConfigErrorCode.NOSE_TANGENCY_EXCEEDS_MAX`, raised at
  P4/P5 construction time (geometry-dependent, so — like P3's hinge-in-OML
  containment check — it can't be a pure P0 schema-load rule).
- Added a hard precondition in `te_cut.py`'s `_loft_region`: every station
  profile must have identical point count before lofting, or the build
  aborts with a clear error (not just a gate test) — a mixed-topology loft
  was part of the original defect's mechanism.
- `tests/configs/devices/te_half_twisted.yaml` (-8° tip twist,
  `hinge_xc=0.72`) is now a **deliberate negative test case** — real
  geometry, correctly rejected — exercised by
  `test_extreme_twist_config_rejected`, not the main P4 build battery.
  `tests/configs/devices/te_half_twisted_moderate.yaml` (-1° tip twist, same
  `hinge_xc`) is the new "max-twist" config that actually passes
  (1.70° measured tangency error) and joins the standard battery.
- Added gates (`tests/gates/test_p04_te_cut.py`): `test_nose_is_single_arc`
  (constant radius on the real built solid, not a min/max band anymore),
  `test_nose_tangency` (now the mean-radius metric), `test_axis_equidistant_
  residual` (reports the derived-axis fit residual), `test_loft_topology_
  uniform`, `test_nose_surface_smoothness` (the direct regression test for
  this bug — a discrete curvature-angle spike-ratio check; measured exactly
  1.0x, i.e. perfectly smooth, on both passing configs post-fix),
  `test_no_unporting`, `test_extreme_twist_config_rejected`.
- Deliberately NOT changed: a literal OCC circular edge
  (`cq.Edge.makeCircle`) for the nose, mixed with straight aft-closing
  edges in one wire, then ruled-lofted across stations. That's unverified
  behavior with no R0 probe backing it, and would risk exactly the
  loft-surface unpredictability the dense-polygon approach (P2's own
  decision) was chosen to avoid. "Single arc, constant curvature" is
  instead verified on the real built solid by checking constant
  radius-from-axis via a live OCC section — same rigor, no new boundary
  risk.
- **Explicitly deferred** (not part of this change): CS internal structure
  (LE spar/web, CS-body end ribs, sandwich skin, TE closeout, counterbalance
  provision, wing-side Ansys reinforcement selections) — all of this maps
  onto plan.md's already-scoped P6 ("Sandwich internals + hardpoints"), P7
  ("Hinges"), and R2 ("Ansys export package"), which build the generic
  spar/rib/sandwich/false-spar/hinge machinery once for every device rather
  than a bespoke CS-only version now. See handoff.md.
- P5 (LE droop) reuses this identical construction (derived axis, single
  arc, angular overlap) via the same `cove_profile.py`/`reference.py`
  machinery — `DeviceWindow` already covers `le_droop` too.
