# Handoff — 2026-07-05
## State
- Release/Phase: R1 / P4 DONE (on branch phase/p04, not yet pushed/PR'd)
- Last green gate: p04 (artifacts/gates/p04.json; regress green: p00–p04)
## Next single action
- Commit P04, push phase/p04, open PR (user merges in GitHub UI). Then branch
  phase/p05, start P5 (LE droop cut, plan.md §8.5 LE path / §9 P5): mirrored
  approach to the TE cut but the droop KEEPS the original airfoil LE (why droop
  beat slats). Gate: 3 watertight bodies (wing + TE CS + LE droop); same
  conservation / shard / tangency criteria as P4. Reuse te_cut's cylinder+box
  construction and booleans.py helpers; add a le_droop config (half-wing).
## Blockers / open questions
- None. SSH push works; PRs merged by user in UI.
## Do not touch
- P0–P4 gates are frozen contracts (docs/gate_changes.md for changes).
- OML = polygon wires + ruled=True (r0_findings/p02.md). Hinge-axis margin uses
  distance-to-SHELL (r0_findings/p03.md). Device cuts: nested cylinders about
  the hinge axis + aft box, volume conserved by set algebra; F4 checked via
  distinct coaxial-cylinder radii, NOT solid↔solid distance (too slow)
  (r0_findings/p04.md).
