<!-- GENERATED from CLAUDE.md by 'make sync-agents' — do not hand-edit. -->

# WingStructGen — Agent Instructions

Full spec: `plan.md` (normative, read the current phase's section before touching
code). This file is the distilled operating rules. `AGENTS.md` is generated
from this file by `make sync-agents` — never hand-edit `AGENTS.md`.

## Session protocol

**START**: read `artifacts/state.json` → `handoff.md` → the current phase's
section in `plan.md` → `make kb-search Q="<phase's domain tags>"` (e.g. the
library/technique names the phase touches — `boolean`, `hinges`, `stl`,
...) and read every match. `docs/kb/` (see `docs/kb/README.md`) is the
knowledge base; `docs/known_issues.md` is a pointer file into it now.

**BEFORE** implementing in an unfamiliar area, or before fighting any
library/API for more than a few minutes: `make kb-search Q="<topic>"`
first — a past session likely already paid this cost.

**AT RESOLUTION** of anything non-obvious (a failed approach, an API
surprise, a design rule just decided): write or update the relevant
`docs/kb/*.md` entry IN THE SAME COMMIT as the fix, then `make kb-index`.
A fight resolved without a KB entry is an incomplete fix.

**END**: rewrite `handoff.md` (never append) — including its `## KB
entries added/updated this session` line, empty is fine but the line must
be present; verify `artifacts/state.json` matches reality; append
`changelog.md` if any decision changed.

## Phase workflow

1. Read the plan.md section for the current phase.
2. Run/write the R0 probe for every third-party boundary the phase touches
   (`scripts/r0_probes/probe_<lib>.py`) — probes call the REAL installed
   library. If a probe contradicts the plan, STOP and update
   `docs/r0_findings/<phase>.md` before writing implementation code. Once a
   probe's finding is durable (not just "confirmed the plan," but a real
   lesson a future phase would otherwise re-learn the hard way), distill it
   into a `docs/kb/*.md` entry — the probe script/`r0_findings` stays as
   raw evidence, the KB entry is what a future session actually reads.
3. Implement.
4. Run the phase gate: `make gate PHASE=p04`.
5. Gate exit 0 → gate writes `artifacts/gates/pXX.json` → commit
   `"P04 DONE: <summary> [gate:pass]"` → proceed. Gate exit != 0 → fix and
   re-run. Never edit a gate to make it pass without logging why in
   `docs/gate_changes.md`.
6. Run `make regress` before declaring the phase complete (this also checks
   `docs/kb/INDEX.md` freshness — fails loudly if a KB entry was added/
   edited without `make kb-index`).
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
  X11 cursor/render libs) — see `docs/kb/libgl-libxcursor-missing-workspace.md`
  for the apt list.

## Where things live

- `docs/conventions.md` — units/frame/sign/naming conventions, single source of truth.
- `docs/kb/` — the knowledge base (durable lessons: OCC workarounds, design
  rules, incidents, format specs). One card per concept; `docs/kb/README.md`
  has the format; `docs/kb/INDEX.md` is generated (`make kb-index`); search
  with `make kb-search Q="term"`. `docs/known_issues.md` is a pointer file
  into this now — don't add new entries there.
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
