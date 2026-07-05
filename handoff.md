# Handoff — 2026-07-05
## State
- Release/Phase: R1 / P3 DONE (on branch phase/p03)
- Last green gate: p03 (artifacts/gates/p03.json; regress green: p00–p03)
## Next single action
- Merge phase/p03 → main (PR), branch phase/p04, start P4 (TE surface cut,
  plan.md §8.5 / §9 P4). R0 FIRST: probe boolean cut + revolution surface on
  a toy solid (fuzzy-value behavior) before implementing. Then: spanwise gap
  cuts + chordwise cut, nose rebuilt as revolution about the TE hinge axis,
  concave cove + false spar, deliberate clearance angle (NEVER exact
  tangency, F4). Gate: exactly 2 watertight bodies; vol(wing)+vol(CS)+vol(gap)
  = vol(P2) within 0.5%; shard filter (F3); no tangent face pairs.
## Blockers / open questions
- Push blocked on nothing now (SSH key live). Waiting on user to merge the
  phase/p03 PR in the GitHub UI (chosen PR flow), then pull main before
  branching phase/p04.
## Do not touch
- P0/P1/P2/P3 gates are frozen contracts (docs/gate_changes.md for changes).
- OML construction is POLYGON wires + ruled=True (docs/r0_findings/p02.md).
- Hinge-axis margin check MUST use distance-to-shell, never distance-to-solid
  (always 0 for interior points) or point-in-solid alone (no margin info) —
  docs/r0_findings/p03.md.
