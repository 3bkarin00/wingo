# ADR-005 — Replace generated-mode lug/tang knuckle hinges with pin-and-tube

**Status**: Accepted (post-P7, pre-P8 kickoff; supersedes ADR's-worth of P7
construction before P8 starts).

## Context

P7 ("Hinges — generated mode", plan.md §9) built each hinge as a LUG
(wing-side) + TANG (CS-side) knuckle pair, piano-hinge-style interleaved
along the axis, each with its own coaxial pin bore
(`backend/geometry/hinges.py`). It passed its gate 6/6 on the first
real-kernel run (`tests/gates/test_p07_hinges.py`, `artifacts/gates/
p07.json`) after 4 rounds of R0 probing documented in `docs/r0_findings/
p07.md` — the lug in particular needed a non-obvious construction (a
keyway carved from a derived, grown-bounding-box copy of `cs_solid`,
since a direct subtraction removes the entire knuckle: CS's real material
reaches all the way to the true axis line).

Before P8 ("Kinematic gate") starts, the design direction changed: the
hinge mechanism moves from discrete lug/tang knuckle pairs to a
pin-and-tube design (WP1, `hinges_pin_tube.py`) — alternating wing-side
and CS-side tube segments on the same axis, each end in a carrier block
bonded to the false spar (wing) or LE web (CS), with the swept clearance
pocket built as a union of rotated copies through ±(max_deflection +
margin) rather than a single revolve. This is a genuine construction-
method pivot for the same physical joint (same axis, same wing/CS split,
same P8 kinematic-sweep consumer), not a new/additional part — the P7
knuckle design is retired, not kept alongside it.

Nothing about P7's own construction was wrong or is being distrusted —
the gate passed cleanly and the export-side re-verification (in-run
coaxiality + clearance checks in `scripts/export_viewer_data.py`) also
passed on a real build in this session. This ADR records a directed
design-direction change, not a technical failure of the lug/tang approach.

Also notable: P7's own work was gate-verified but had **not yet been
committed to git** when this pivot happened (still sitting as uncommitted/
untracked changes on `phase/p07` — `handoff.md`'s claim that "every P7
commit pushed to origin" was inaccurate, caught while investigating this
pivot). The lug/tang code is therefore being replaced before it ever
reached `main`, not reverted out of history.

## Decision

Retire the P7 lug/tang construction and replace it with WP1's pin-and-tube
design, same phase slot (P7) in the phase sequence — no renumbering, same
precedent as ADR-004's "gaps cost nothing" reasoning:

- `backend/geometry/hinges.py` (lug/tang, never committed) is replaced by
  `backend/geometry/hinges_pin_tube.py` (wing/CS tube segments + carriers
  + rotated-copy swept pockets + access bore + set-screw).
- `tests/gates/test_p07_hinges.py` is replaced by a new gate exercising the
  pin-and-tube construction's own pass criteria (coaxiality, clearance,
  swept-pocket sweep-through-deflection non-interference, carrier bond to
  false spar / LE web) — P7's gate artifact (`artifacts/gates/p07.json`)
  will be regenerated against the new construction, not hand-edited; this
  is a full gate replacement, logged here rather than in
  `docs/gate_changes.md` (that file is for edits to gates that keep their
  original construction target — this is a construction-target swap).
- `docs/r0_findings/p07.md`'s existing lug/tang probe trail is kept as
  historical record (same posture as ADR-004 keeping ADR-002/ADR-003's
  stale LE-droop mentions) — a new R0 probe trail for WP1's sweep-with-
  spine / offset-curve-on-surface / rotated-copy-union APIs is appended
  under its own heading, not overwriting the old trail.
- `backend/tolerances.py` "Hinges, generated mode" section
  (`HINGE_PIN_DIA_MM`, `HINGE_KNUCKLE_WALL_MM`, `HINGE_KNUCKLE_LEN_MM`,
  `HINGE_KNUCKLE_AXIAL_GAP_MM`, `HINGE_LUG_CLEARANCE_MARGIN_MM`,
  `HINGE_MOUNT_OVERLAP_MM`) is retired; WP1 introduces its own tolerance
  set (tube/carrier wall, bond gap, pocket clearance, overlap margin, set-
  screw diameter) with fresh derivation comments — not a rename, since the
  geometry itself is different (no knuckle wall, no axial interleave gap
  in the same sense).
- `tools/viewer/app.js`'s "Hinge lugs"/"Hinge tangs" layer toggles are
  replaced by carrier/tube ROLE-typed layers (plan.md's viewer body-tree
  update, per the WP1-WP2c "PIPELINE INTEGRATION" spec).
- `scripts/export_viewer_data.py`'s hinge re-verification block (lug/tang
  coaxiality + clearance) is replaced with the equivalent check against
  pin-and-tube bodies.
- `handoff.md`'s "Do not touch" entries describing the lug/tang
  construction (the `cs_notched` keyway rationale, the "NOT a boolean
  subtraction from `cs_solid`" warning) are removed — they describe a
  construction path that no longer exists. `handoff.md` also gets a
  truthful rewrite of its git/push claims per this ADR's Context section.

## Consequences

- P7's phase slot is rebuilt, not retired (unlike P5/LE-droop in ADR-004)
  — plan.md §9's P7 scope text changes from "lug/tang knuckle pair" to
  "pin-and-tube" but keeps its phase number and pass-criteria shape
  (coaxiality + clearance, now against the new bodies).
- D9 (`plan.md` §2, "Hinges") stays "Generated printable OR COTS placeholder
  pockets (pin Ø param), configurable" — unchanged at the decision-table
  level, since D9 was already agnostic to the specific generated-mode
  construction method; only the generated-mode implementation swaps.
- No schema change from this ADR alone (`te_surface.hinges.mode:
  generated` still means "build real printable hinge hardware" — WP1 is
  what "generated" now means, not a new mode value). WP2/WP2b/WP2c are
  separate, unrelated additions (spar shapes, π-joint ribs, tab-and-slot
  interlock) tracked in their own plan.md entries, not this ADR.
- The P7 gate is NOT a frozen contract going forward in the sense
  `handoff.md` previously asserted (frozen since authored fresh, never
  modified after the fact) — this ADR is itself the one modification, same
  "logged, not silent" posture the project requires for any gate change.
- Face identity for FEA naming (tube/carrier bond faces) now goes through
  the new shared centroid-registry mechanism (WP1/WP2b/WP2c's common
  module) instead of P7's ad hoc "no naming yet" state — P7 never reached
  the STEP/XDE naming phase, so there is no prior naming contract to
  preserve here.
