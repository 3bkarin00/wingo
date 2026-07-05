# Conventions

Single source of truth for units, frames, signs, and naming. Referenced
everywhere — code, gates, docs. If code and this file disagree, this file
wins and the code is a bug.

## Units

mm, deg. Every schema field is suffixed to make the unit unambiguous at the
call site: `_mm`, `_deg`, `_frac` (dimensionless fraction 0..1), `_xc`
(chordwise fraction 0..1 measured from LE). `.cdb` decks declare **mm–tonne–s**
in their header block, and this unit system is asserted (not assumed) in the
P13 gate and stated in the P19 report (F8 — unit mismatch is a 10^9 error).

## Frame

X aft, Y starboard, Z up, right-handed. Origin: center-section root leading
edge.

## Twist axis

User-declared per config as `twist_axis_xc`, stored on every section. Never
implicit — a section's twist rotation is always about this declared fraction
of local chord, never assumed to be LE, TE, or quarter-chord unless the user
set it to that value.

## Hinge / latch axes

Derived FIRST as perfectly straight 3D lines; every hinge mechanism is then
defined relative to its axis, never the reverse (the axis is not "wherever
the mechanism ends up").

## Signs

- TE (trailing-edge) control surface: trailing-edge-down is positive deflection.
- LE (leading-edge) droop nose: leading-edge-down is positive deflection.

## Airfoils

Unit chord. Point ordering: TE → upper → LE → lower → TE. Blunt TE enforced
to `te_min_thickness_mm`. Identical cosine resampling (`resample_points`,
always odd) applied before any placement, regardless of source (NACA
generator, UIUC snapshot, or `.dat` upload) — this is what makes sections
from different sources comparable and lofting well-defined.

## Naming contract

`SEG-{C|L|R}/BODY-{name}/ROLE-{skin|rib|spar|...}` — applied consistently
across STEP, `.cdb`, glTF, DXF, and the report, so a component can be
identified by the same name regardless of which output format you're looking
at (P9's gate checks names survive a STEP re-import; P13's oracle parser
checks CMBLOCK names match this contract).
