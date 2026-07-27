# Handoff — 2026-07-22

## State
- **R1 is fully gate-complete.** Every R1 gate (P0–P4, P6, P7, P8, P9,
  P10) is real, green, and committed on `phase/p07`
  (`artifacts/gates/pXX.json`, `artifacts/state.json.gates_passed` =
  `[p00,p01,p02,p03,p04,p06,p08,p09,p07,p10]`). `make regress` then
  re-ran all 10 gates together for real on wingo.coder (21:35→00:24
  UTC, 2h49m): **104/104 tests passed, 0 failures.** Per-suite: p00
  7/7 (0.96s), p01 8/8 (0.25s), p02 9/9 (4.57s), p03 16/16 (31.56s),
  p04 25/25 (5:12), p06 22/22 5 warnings (1:15:48 — the two slowest
  suites are p06 and p08 by construction, not a regression), p08 3/3
  (41:51), p09 3/3 (6.86s), p07 7/7 (18:55), p10 4/4 (26:52). No
  regressions from later phases into earlier ones.
- P10 stack live-verified end-to-end (job → build → export → serve →
  browser render → deflection kinematics matches server) on the real
  API/worker/browser, not mocked.
- 5-hour autonomous cycles armed in the Mac Claude session (cron; checks
  `origin/phone-notes` NOTES.md for user instructions from their iPhone
  first, then advances the gate queue). Progress artifact (status board
  + embedded 3D viewer, https://claude.ai/code/artifact/e95794cd-3ea9-
  49f9-99d2-a66905efcf06) is FULLY REFRESHED: final regress numbers,
  all-green gate rail, and a fresh `te_half` export (D24 π-joints, D25
  interlock, pin-and-tube hinges, current as of 2026-07-22 01:12 UTC).
- `kb-scaffold` branch (docs/kb knowledge base, 27 entries + make
  kb-index/kb-search + regress staleness check) pushed, awaiting merge.

## Next single action
- **HOLD — user is manually testing the tool 2026-07-22. Do NOT start
  P11 (no R0 probes, no implementation) until they give a go-ahead.**
  This is recorded on `origin/phone-notes` NOTES.md too — check it
  every cycle, it's the override channel. All queued non-P11 bookkeeping
  is DONE (artifact refresh, known_issues, handoff, changelog) — there
  is currently nothing else queued. If a cron cycle fires and finds this
  hold still in place with nothing new on phone-notes, the correct
  action is to do nothing (or re-check for a go-ahead a while later),
  not to invent busywork.
- Once the user gives the go-ahead: start **P11 (3-piece wing
  segmentation, R1.5)** per plan.md §9: read plan.md §8 step 6 (already
  re-read this session) + the P11 gate criteria, R0-probe any new OCC
  boundary (tongue/box body construction, break-plane cuts — likely
  reuses existing spar-shape footprint functions from D23, nothing
  fictional-API-shaped expected but probe anyway per the hard rule),
  implement, `make gate PHASE=p11`, then `make regress` again (P11's
  own gate criteria requires P2–P10 green in segmented mode).

## KB entries added/updated this session
- All 27 seed entries live on `kb-scaffold` (not yet on this branch).
  Owed once merged: tessellate-vertex-dedup, P8 axial-gap-vs-skin-gap
  lesson, workspace-restart recovery sequence, rsync-clobbering-state
  lesson, three.js slash-stripping, glTF Y-up parent-frame lesson.

## Blockers / open questions
- **User-imposed hold on P11**, not a technical blocker — see above.
- wingo.coder workspace container got recreated again post-regress
  (agent connection lost mid the viewer-data export, no restart command
  issued) — recovered per docs/known_issues.md's now-expanded libGL
  entry (apt-get update THEN install, then `make up`); long runs use
  setsid + logs in ~/ (persistent volume), never /tmp.
- New, unresolved, non-blocking finding: `te_half_twisted_moderate.yaml`
  fails a sandwich core watertightness check — outside the P6 gate's
  own deliberate te_half-only battery scope, logged in known_issues.md,
  worth a look during/before P11 since segmentation cuts through the
  same construction.

## Do not touch
- P0-P4, P6, P7, P8, P9, P10 gates frozen (docs/gate_changes.md).
- Never edit frozen P4 cs_solid/P6 bodies in place — hinges return
  derived pocketed bodies; pipeline.py must keep exporting THOSE.
- artifacts/state.json only updates on a real green gate (conftest.py).
  `make regress` does NOT write it (no PHASE env var) — that's correct,
  it's a confirmation run, not a new gate.
