---
title: An unmatched shell glob reaches pytest as a literal path, not zero files
tags: [pytest, tooling, subprocess, incident]
source: "docs/known_issues.md (migrated); scripts/run_regress.py"
phase: p00
confidence: verified
last_updated: 2026-07-19
---

`subprocess.run([pytest, "tests/gates/test_p00_*.py"])` does NOT shell-expand
the glob — pytest receives the literal string with the `*` still in it and
exits 2 ("file or directory not found"). The Makefile `gate` target happens
to work because `make` runs the recipe through a shell that expands the
glob; `scripts/run_regress.py` used `subprocess.run` directly (no shell) and
the same pattern silently failed there.

Fix: always expand gate-file globs in Python (`Path.glob(...)`) before
handing concrete paths to pytest, and guard with an existence check — if a
phase is marked passed in `state.json` but no gate file matches, fail LOUDLY
(this is exactly the corrupt-state / lost-gate case, not a "nothing to run"
case). See `scripts/run_regress.py`'s own `GATES_DIR.glob(f"test_{phase}_*.py")`
+ explicit empty-match FATAL check.
