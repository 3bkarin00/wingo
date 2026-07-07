# Handoff — 2026-07-07
## State
- Release/Phase: R1 / P4 DONE for real this time (on branch phase/p04, not
  yet committed/pushed/PR'd) — the refined per-station arc construction
  (ADR-002) now has an actual fresh gate pass; the artifact on disk before
  today was stale (recorded against P4-v1's cylinder construction).
- Last green gate: p04 (artifacts/gates/p04.json, timestamp 2026-07-07;
  regress green: p00–p04).
## Next single action
- Commit P4 (construction + audit fixes + test-architecture overhaul, see
  changelog.md 2026-07-07), push phase/p04, open PR (user merges in GitHub
  UI). Then branch phase/p05, start P5 (LE droop cut, plan.md §8.5 LE path /
  §9 P5): apply the IDENTICAL per-station arc construction
  (cove_profile.py) to the LE droop hinge, same tolerances unless a config
  overrides. Gate: 3 watertight bodies (wing + TE CS + LE droop); same
  conservation/shard/tangency/clearance criteria as P4. Reuse te_cut.py's
  build/finish split and geometry_cache.py pattern for the LE gate too —
  don't rebuild the lazy-fixture/cache/timing machinery from scratch, adapt
  it.
## Blockers / open questions
- None. SSH push works; PRs merged by user in UI.
## Do not touch
- P0–P4 gates are frozen contracts (docs/gate_changes.md for changes).
- OML = polygon wires + ruled=True (r0_findings/p02.md). Hinge-axis margin
  uses distance-to-SHELL (r0_findings/p03.md).
- Device cove/nose = per-station axis-centered arcs, NOT cylinders (ADR-002,
  supersedes the "Do not touch" note from 2026-07-05): nose arc(s) pass
  through the normal-foot on each skin (tangent by construction); cove is a
  concentric arc offset by the fixed `COVE_CLEARANCE_MM` (5mm), invariant
  under rotation about the hinge axis. `gap_mm` is a SEPARATE, orthogonal
  spanwise-inset clearance — it no longer sizes the radial nose/cove gap.
- Gate tests build geometry through `tests/gates/geometry_cache.py`
  (lazy, indirect-parametrized `cut_result`/`cut_result_fresh` fixtures), not
  an eager multi-config dict fixture — a `-k <stem>` run must only ever build
  that one config. Never re-run a full geometry-build gate as a stopwatch to
  answer a performance question: read `artifacts/gates/p04_timings.json`
  (per-stage) or `--durations=20` (per-test, already on by default via
  `make gate`/regress) instead — both exist precisely so a slow-config
  question never costs another multi-minute rebuild loop.
- `te_half_twisted` legitimately costs ~145s to build cold (2-4x untwisted,
  real OCC boolean cost from the tilted station planes, not a bug) — see
  docs/known_issues.md. This is expected; don't "fix" it by reducing
  N_STATIONS/arc density without a new measurement showing it's actually
  needed (nothing currently exceeds the 600s `GEOMETRY_TEST_TIMEOUT_S`
  budget with less than ~4x margin).
