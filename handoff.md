# Handoff — 2026-07-19

## State
- Release/Phase: R1 / P6 DONE (`artifacts/gates/p06.json`, `gates_passed`
  through p06 — see `artifacts/state.json`). P7 (hinges) is in progress on
  branch `phase/p07`, separate from this branch.
- THIS session (branch `kb-scaffold`, infra-only, explicitly no geometry
  work): scaffolded `docs/kb/`, a file-based knowledge base — 27 seed
  entries (migrated `docs/known_issues.md` + mined `docs/r0_findings/`,
  ADR-001–005, plan.md's failure-mode register), `make kb-index`/`make
  kb-search`, a staleness check in `make regress`, and CLAUDE.md session-
  protocol wiring (kb-search before fighting a library; write/update a KB
  entry in the SAME COMMIT as any non-obvious fix). See changelog.md
  2026-07-19 entry.

## Next single action
- Merge/review `kb-scaffold`, then resume P7 — Hinges (generated mode) on
  `phase/p07`: "hinge holes coaxial within 0.05mm; carrier clearance to
  the moving body >= configured fit gap." `config.hinges` schema fields
  already exist; P3 builds the hinge AXIS, not hardware/holes yet.

## KB entries added/updated this session
- All 27 entries under `docs/kb/` are new this session — see
  `docs/kb/INDEX.md`. Going forward this line should list a short delta,
  not "everything."

## Blockers / open questions
- None technical.

## Do not touch
- P0-P4, P6 gates frozen (docs/gate_changes.md).
- `docs/kb/INDEX.md` is GENERATED (`make kb-index`) — never hand-edit it.
