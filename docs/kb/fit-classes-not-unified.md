---
title: "Bonded / sliding / locating fits are different physics — never unify their tolerance constants"
tags: [tolerances, design-rule, fits]
source: "backend/tolerances.py PI_BOND_GAP_MM, HINGE_CARRIER_BOND_GAP_MM, SPAR_RIB_CUTOUT_CLEARANCE_MM, interlock.fit_clearance_mm derivation comments; backend/schema/models.py AlignmentPins.fit"
phase: p06
confidence: verified
last_updated: 2026-07-19
---

This project deliberately keeps SEPARATE tolerance constants for physically
different fit classes, even when two values happen to be numerically close
— resist the urge to "simplify" by unifying them:

- **Bonded, non-locating** (adhesive-filled gap, nothing registers against
  it): `PI_BOND_GAP_MM` = `HINGE_CARRIER_BOND_GAP_MM` = 0.2mm — deliberately
  the SAME value (one shared "structural adhesive film thickness" constant,
  reused, not coincidence) because both really are the same physics.
- **Plain clearance cutout, non-locating** (a cutout the part just needs to
  fit through, nothing keys off it precisely): `SPAR_RIB_CUTOUT_CLEARANCE_MM`
  = 0.2mm — same magnitude as the bonded gap but for a DIFFERENT reason
  (CNC/laser slip-fit allowance), and deliberately 2x the interlock's
  default `fit_clearance_mm` (0.1mm) for a THIRD reason: a plain cutout is
  non-locating, while a D25 tab/slot pair IS a locating feature and wants a
  tighter fit.
- **Sliding/press mechanical fits** (real assembly hardware, e.g. mold
  alignment pins): `schema.AlignmentPins.fit: Literal["sliding", "press"]`
  — a user-selectable CATEGORY, not a single numeric constant at all, since
  the tightness genuinely depends on the choice.

The pattern to follow when adding a new fit-dependent dimension: ask
"bonded, locating-clearance, or mechanical-sliding/press?" before reusing
an existing constant — a numeric coincidence between two current values is
not evidence they should be merged into one, and a future change to one
physics class must never silently change the other.
