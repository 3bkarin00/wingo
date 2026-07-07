# WingStructGen — Agent Instructions

Full spec: `plan.md` (normative, read the current phase's section before touching
code). This file is the distilled operating rules. `AGENTS.md` is generated
from this file by `make sync-agents` — never hand-edit `AGENTS.md`.

## Session protocol

**START**: read `artifacts/state.json` → `handoff.md` → the current phase's
section in `plan.md` → skim `docs/known_issues.md` for the libraries this
phase touches.

**END**: rewrite `handoff.md` (never append); verify `artifacts/state.json`
matches reality; append `changelog.md` if any decision changed; log any new
OCC workaround in `docs/known_issues.md`.

## Phase workflow

1. Read the plan.md section for the current phase.
2. Run/write the R0 probe for every third-party boundary the phase touches
   (`scripts/r0_probes/probe_<lib>.py`) — probes call the REAL installed
   library. If a probe contradicts the plan, STOP and update
   `docs/r0_findings/<phase>.md` before writing implementation code.
3. Implement.
4. Run the phase gate: `make gate PHASE=p04`.
5. Gate exit 0 → gate writes `artifacts/gates/pXX.json` → commit
   `"P04 DONE: <summary> [gate:pass]"` → proceed. Gate exit != 0 → fix and
   re-run. Never edit a gate to make it pass without logging why in
   `docs/gate_changes.md`.
6. Run `make regress` before declaring the phase complete.
7. Close the session per the protocol above.

## Hard rules

- Never mock the third-party boundary a gate verifies. Gates run the real
  CadQuery/OCP kernel, real Gmsh, real ezdxf, real lualatex, on real files.
- Never mark a phase done without a gate artifact in `artifacts/gates/`.
- Never hardcode geometry results (volumes, counts, coordinates) into gates
  as magic constants — golden-config expected values live in
  `tests/golden/expected/*.json` with provenance notes.
- Never use OCC shell/thicken for the IML (F1). Never exact tangency in
  booleans (F4). Never skip the shard filter after a boolean (F3).
- Never invent an API — if unsure of a signature, run the R0 probe.
- Never re-run a full geometry-build gate to answer a question that
  instrumentation, the geometry build cache, or a single parametrized test
  can answer instead. Gate tests build geometry through
  `tests/gates/geometry_cache.py` (per-config, lazy — a `-k <stem>` run must
  build only that config); per-stage construction timings land in
  `artifacts/gates/pXX_timings.json` on every real build, and `--durations=20`
  runs on every `make gate`/`make regress`. Diagnose a slow config by reading
  those, not by watching a terminal.
- All units mm/deg; all frames per `docs/conventions.md`. No implicit conventions.
- Every numeric tolerance lives in `backend/tolerances.py` with a derivation
  comment — a tolerance literal anywhere else is a review-blocking offense.
- Ask the human only when the plan is ambiguous or a gate must change;
  otherwise proceed autonomously through the phase sequence.

## Environment noise (not errors)

- Gates run on the `wingo.coder` Coder workspace (Docker + cadquery/gmsh);
  the Mac is the git source of truth, synced via rsync.
- The `version mismatch: client v2.34.3 / server v2.29.6 ...` banner printed
  on every `coder`/`ssh wingo.coder` command is benign Coder CLI/server
  version-skew noise, unrelated to the build. Ignore it — never treat it as a
  failure or try to "fix" it. Judge success by the command's own exit code
  and output.
- cadquery/OCP/gmsh need native libs on a bare Ubuntu workspace (libGL,
  X11 cursor/render libs) — see `docs/known_issues.md` for the apt list.

## Where things live

- `docs/conventions.md` — units/frame/sign/naming conventions, single source of truth.
- `docs/known_issues.md` — OCC workaround knowledge base (symptom → cause → workaround → phase).
- `docs/decisions/ADR-*.md` — one record per post-kickoff pivot.
- `docs/r0_findings/pXX.md` — per-phase probe results.
- `docs/gate_changes.md` — any audited gate modification, with reason.
- `backend/tolerances.py` — every numeric tolerance in the tool.
- `handoff.md` — next single action, hard cap ~20 lines, rewritten not appended.
- `artifacts/state.json` — machine-readable phase/gate state (read this for
  STATE; read `handoff.md` for INTENT — never parse prose for state).
- `tests/gates/geometry_cache.py` — disk cache for expensive OCC boolean
  construction output (keyed on config + geometry-module source hash), used
  by gate fixtures only; never by production/worker code, which always
  builds fresh. `artifacts/cache/` (gitignored) holds the cached `.brep`s.
- `artifacts/gates/pXX_timings.json` — per-stage construction timings from
  the last real (non-cached) build of each config, for diagnosing a slow
  gate without re-running it.
