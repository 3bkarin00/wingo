#!/usr/bin/env python3
"""Re-run every gate already recorded as passed in artifacts/state.json.

Later phases must not break earlier gates (plan.md §0.1 step 6). This reads
gates_passed from the state file rather than globbing all test files, so a
phase that's mid-development (test file exists, not yet green) doesn't get
swept into the regression run.

Gate files are collected with Python's glob (NOT by handing a shell pattern
to pytest). A subprocess call does no shell expansion, so passing the literal
string "tests/gates/test_p00_*.py" makes pytest look for a file with a
`*` in its name and exit 2 — see docs/known_issues.md. If a phase is marked
passed in state.json but no gate file exists, that's a corrupt state / lost
gate, so we fail LOUDLY rather than let an unmatched glob leak through.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "artifacts" / "state.json"
GATES_DIR = ROOT / "tests" / "gates"


def main() -> int:
    state = json.loads(STATE_PATH.read_text())
    gates_passed = state.get("gates_passed", [])
    if not gates_passed:
        print("no gates recorded as passed yet — nothing to regress")
        return 0

    failures = []
    for phase in gates_passed:
        gate_files = sorted(GATES_DIR.glob(f"test_{phase}_*.py"))
        if not gate_files:
            print(
                f"FATAL: phase {phase} is marked passed in state.json but no gate "
                f"tests exist ({GATES_DIR}/test_{phase}_*.py). State is corrupt or a "
                f"gate file was lost — refusing to silently skip it."
            )
            return 1

        rel = [str(p.relative_to(ROOT)) for p in gate_files]
        print(f"--- regress: {phase} ({', '.join(rel)}) ---")
        result = subprocess.run(
            [str(ROOT / ".venv" / "bin" / "pytest"), *rel, "-v", "--durations=20"], cwd=ROOT
        )
        if result.returncode != 0:
            failures.append(phase)

    if failures:
        print(f"REGRESSION FAILURE in: {', '.join(failures)}")
        return 1
    print(f"all {len(gates_passed)} prior gate(s) still green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
