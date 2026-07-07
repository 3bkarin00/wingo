# Handoff — 2026-07-07
## State
- Release/Phase: R1 / P4 DONE (on branch phase/p04, not yet committed/
  pushed/PR'd) — construction redesigned twice this session: ADR-002 (per-
  station arcs replace cylinders), then ADR-003 (single arc + derived
  hinge-axis height replaces the two-arc/Hermite blend that turned out to
  render visibly lumpy on any twisted config).
- Last green gate: p04 (artifacts/gates/p04.json, 25 tests; regress green:
  p00–p04).
## Next single action
- Commit P4 (ADR-003 redesign + full gate rewrite, see changelog.md
  2026-07-07 "later" entry), push phase/p04, open PR (user merges in GitHub
  UI). Then branch phase/p05, start P5 (LE droop cut, plan.md §8.5 LE path /
  §9 P5): apply the IDENTICAL construction (derived axis height, single
  arc, anti-unporting overlap — cove_profile.py/reference.py already handle
  `le_droop` via the shared `DeviceWindow` schema type) to the LE droop
  hinge. Gate: 3 watertight bodies (wing + TE CS + LE droop); same
  conservation/shard/tangency/clearance/no-unporting criteria as P4. Reuse
  te_cut.py's build/finish split and geometry_cache.py pattern — don't
  rebuild the lazy-fixture/cache/timing machinery from scratch, adapt it.
## Blockers / open questions
- None. SSH push works; PRs merged by user in UI.
## Deferred scope (explicit, not forgotten)
- CS internal structure (LE spar/web carrying hinge tangs, CS-body end
  ribs, sandwich skin with core ramp-out, TE closeout wedge, optional
  counterbalance mass-rod channel, wing-side Ansys reinforcement named
  selections) was scoped in detail during this session's redesign request
  but DEFERRED per explicit user decision — it maps directly onto phases
  plan.md already assigns: P6 "Sandwich internals + hardpoints" (generic
  spar/rib/sandwich/false-spar machinery for every device, not a bespoke
  CS-only version), P7 "Hinges" (tangs, lug clearance), R2 "Ansys export
  package" (named selections). Build it there, not by pulling it into P4/P5.
## Do not touch
- P0–P4 gates are frozen contracts (docs/gate_changes.md for changes).
- OML = polygon wires + ruled=True (r0_findings/p02.md). Hinge-axis margin
  uses distance-to-SHELL (r0_findings/p03.md).
- Device cove/nose = SINGLE per-station axis-centered arc (ADR-003,
  supersedes ADR-002's two-arc branch — that branch is DELETED, not just
  unused): nose is one arc at R=(Ru+Rl)/2, extended angularly beyond Pu/Pl
  by max_deflection+OVERLAP_MARGIN_DEG (anti-unporting). The hinge axis
  HEIGHT is DERIVED (backend/geometry/reference.py `derive_hinge_axis`,
  least-squares fit to the true equidistant-from-skin point at 24
  stations) — never read straight off a 2-point camber-line mean again;
  that was the actual root cause of the lumpy nose, not twist per se.
  Config-time validation (NOSE_TANGENCY_MAX_DEG=2.0°) REJECTS a config
  whose twist/hinge_xc combination can't keep Ru≈Rl close enough — this is
  intentional fail-fast behavior, not a bug if a new device config gets
  rejected; the error message says what to change.
- Gate tests build geometry through `tests/gates/geometry_cache.py`
  (lazy, indirect-parametrized `cut_result`/`cut_result_fresh` fixtures), not
  an eager multi-config dict fixture — a `-k <stem>` run must only ever build
  that one config. Never re-run a full geometry-build gate as a stopwatch to
  answer a performance question: read `artifacts/gates/p04_timings.json`
  (per-stage) or `--durations=20` (per-test, already on by default via
  `make gate`/regress) instead.
- `tests/configs/devices/te_half_twisted.yaml` is a DELIBERATE negative
  test case now (-8° tip twist, correctly rejected by validation) — it is
  NOT part of the "must successfully build" battery and never will build a
  real boolean (fails fast at station-data validation, milliseconds, not
  the ~145s a real build would cost). Don't "fix" it to build; that's the
  point of `te_half_twisted_moderate.yaml` instead. If plan.md eventually
  wants an even harder twisted stress case, add a new config, don't repurpose
  this one.
