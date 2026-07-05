"""Gate artifact writer.

On a fully-green run of a phase's gate tests, writes artifacts/gates/pXX.json
and inserts a gate_results row (§7 — the report renders from this table, so
gates and reporting cannot diverge, per plan.md). PHASE is read from the
PHASE env var the Makefile exports (`make gate PHASE=p00`), not parsed from
test file names, so it's unambiguous.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS_GATES = ROOT / "artifacts" / "gates"
STATE_PATH = ROOT / "artifacts" / "state.json"

_metrics: dict = {}


@pytest.fixture
def gate_metrics() -> dict:
    """Tests write phase metrics into this shared dict; collected at session end."""
    return _metrics


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    phase = os.environ.get("PHASE")
    if not phase:
        return  # not invoked via `make gate PHASE=pXX` — nothing to record

    passed = exitstatus == 0
    artifact = {
        "phase": phase,
        "pass": passed,
        "metrics": _metrics,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    ARTIFACTS_GATES.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_GATES / f"{phase}.json").write_text(json.dumps(artifact, indent=2))

    if not passed:
        return  # only a green gate updates state / gate_results (§0.1 step 5)

    from backend.schema.db import session_scope
    from backend.schema.db_models import GateResultRow

    with session_scope() as db_session:
        db_session.add(
            GateResultRow(phase=phase, name=f"gate_{phase}", passed=True, metrics=_metrics)
        )

    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text())
    else:
        state = {
            "schema_version": "0.4",
            "current_release": "R1",
            "current_phase": phase,
            "gates_passed": [],
            "last_golden_run": None,
            "plan_md_version": "0.4",
        }

    if phase not in state["gates_passed"]:
        state["gates_passed"].append(phase)
    state["current_phase"] = phase
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")
