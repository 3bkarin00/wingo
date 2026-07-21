# Handoff — 2026-07-21

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
  + embedded 3D viewer) republishes to a stable claude.ai URL — **still
  showing pre-R1-close state, needs a refresh** (see next action).
- `kb-scaffold` branch (docs/kb knowledge base, 27 entries + make
  kb-index/kb-search + regress staleness check) pushed, awaiting merge.

## Next single action
- Refresh the progress artifact (same claude.ai URL, same file path)
  with the real regress numbers above, replacing any "running"
  placeholders. Then, if remote CPU allows, re-export
  `artifacts/viewer_data.json` via `scripts/export_viewer_data.py` on
  wingo.coder (current embedded viewer is a stale July-14 snapshot,
  predates D23–D25 interlock/π-joints and the pin-and-tube hinges) and
  rebuild the embedded 3D viewer from it.
- Then start **P11 (3-piece wing segmentation, R1.5)** per plan.md §9:
  read plan.md §8 step 6 (already re-read this session) + the P11 gate
  criteria, R0-probe any new OCC boundary (tongue/box body construction,
  break-plane cuts — likely reuses existing spar-shape footprint
  functions from D23, nothing fictional-API-shaped expected but probe
  anyway per the hard rule), implement, `make gate PHASE=p11`, then
  `make regress` again (P11's own gate criteria requires P2–P10 green
  in segmented mode).

## KB entries added/updated this session
- All 27 seed entries live on `kb-scaffold` (not yet on this branch).
  Owed once merged: tessellate-vertex-dedup, P8 axial-gap-vs-skin-gap
  lesson, workspace-restart recovery sequence, rsync-clobbering-state
  lesson, three.js slash-stripping, glTF Y-up parent-frame lesson.

## Blockers / open questions
- None blocking. wingo.coder workspace restarted twice earlier this
  session (agent lost) — recovery per docs/known_issues.md libGL entry
  + `make up`; long runs use setsid + logs in ~/ (persistent volume),
  never /tmp — this held up fine through the full regress run.

## Do not touch
- P0-P4, P6, P7, P8, P9, P10 gates frozen (docs/gate_changes.md).
- Never edit frozen P4 cs_solid/P6 bodies in place — hinges return
  derived pocketed bodies; pipeline.py must keep exporting THOSE.
- artifacts/state.json only updates on a real green gate (conftest.py).
  `make regress` does NOT write it (no PHASE env var) — that's correct,
  it's a confirmation run, not a new gate.
