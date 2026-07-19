# Handoff — 2026-07-20

## State
- R1 / P6 ext + P7 + P8 + P9 + P10 all IMPLEMENTED on `phase/p07`
  (committed per-phase this session). Gate truth: **p09 GREEN**
  (artifacts/gates/p09.json, real run). p08 RUNNING on wingo.coder
  (~/p08.log — test 1/3 passed; skin-clearance sweep in progress, slow
  by design: 141 full-body booleans). p07's committed artifact is the
  RETIRED lug/tang record (ADR-005) — fresh pin-and-tube run queued.
  p06 full tier queued (fast tier green). p10 gate written, not yet run.
- P10 stack live-verified end-to-end (job → build → export → serve) on
  the real API/worker; frontend type-checks + builds (npm run build).
- 5-hour autonomous cycles armed in the Mac Claude session (cron; checks
  `origin/phone-notes` NOTES.md for user instructions from their iPhone
  first, then advances the gate queue). Progress artifact (status board
  + embedded 3D viewer) republishes to a stable claude.ai URL.
- `kb-scaffold` branch (docs/kb knowledge base, 27 entries + make
  kb-index/kb-search + regress staleness check) pushed, awaiting merge.

## Next single action
- Read ~/p08.log on wingo.coder. If green: pull p08.json, commit
  "P08 DONE ... [gate:pass]", then launch P7 fresh
  (`PHASE=p07 setsid nohup .venv/bin/pytest tests/gates/test_p07_hinges.py
  -v --durations=20 > ~/p07.log`), then P6 full, then P10 E2E, then
  `make regress` — one at a time, they share one CPU.

## KB entries added/updated this session
- All 27 seed entries live on `kb-scaffold` (not yet on this branch).
  Owed once merged: tessellate-vertex-dedup, P8 axial-gap-vs-skin-gap
  lesson, workspace-restart recovery sequence.

## Blockers / open questions
- wingo.coder workspace restarted twice mid-run (agent lost) — recovery
  per docs/known_issues.md libGL entry + `make up`; long runs now use
  setsid + logs in ~/ (persistent volume), never /tmp.

## Do not touch
- P0-P4, P6 gates frozen (docs/gate_changes.md).
- Never edit frozen P4 cs_solid/P6 bodies in place — hinges return
  derived pocketed bodies; pipeline.py must keep exporting THOSE.
- artifacts/state.json only updates on a real green gate (conftest.py).
