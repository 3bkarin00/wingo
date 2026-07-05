"""P0 gate — plan.md §9 pass criteria:

  every invalid config in tests/configs/invalid/ rejected with the expected
  error code; valid configs round-trip schema->JSON->schema losslessly; a
  gate test SIGKILLs a worker subprocess mid-job and asserts the job lands
  in FAILED with a checkpoint, not RUNNING.

Runs against the REAL Postgres + Redis from docker-compose (§0.2 — never
mock the boundary a gate verifies), started via `make up`.
"""
import os
import signal
import time
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from backend.schema.db import session_scope
from backend.schema.models import Config
from backend.worker import jobs as job_ops
from backend.worker import sandbox

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INVALID_DIR = REPO_ROOT / "tests" / "configs" / "invalid"
VALID_DIR = REPO_ROOT / "tests" / "configs" / "valid"

invalid_fixtures = sorted(INVALID_DIR.glob("*.yaml"))
valid_fixtures = sorted(VALID_DIR.glob("*.yaml"))


@pytest.mark.parametrize("fixture_path", invalid_fixtures, ids=lambda p: p.stem)
def test_invalid_config_rejected_with_expected_code(fixture_path: Path, gate_metrics: dict) -> None:
    data = yaml.safe_load(fixture_path.read_text())
    expected_code = data.pop("expected_error_code")

    with pytest.raises(ValidationError) as exc_info:
        Config.model_validate(data)

    assert f"[{expected_code}]" in str(exc_info.value), (
        f"{fixture_path.name}: expected error code '{expected_code}' not found in "
        f"{exc_info.value}"
    )
    gate_metrics.setdefault("invalid_configs_rejected", []).append(fixture_path.stem)


@pytest.mark.parametrize("fixture_path", valid_fixtures, ids=lambda p: p.stem)
def test_valid_config_round_trips_losslessly(fixture_path: Path, gate_metrics: dict) -> None:
    data = yaml.safe_load(fixture_path.read_text())
    original = Config.model_validate(data)

    round_tripped = Config.model_validate_json(original.model_dump_json())

    assert round_tripped == original, f"{fixture_path.name} did not round-trip losslessly"
    gate_metrics.setdefault("valid_configs_round_tripped", []).append(fixture_path.stem)


def _dummy_job_stage(_job_id, checkpoint_writer) -> None:
    """Module-level (picklable for 'spawn') stage: writes one checkpoint,
    then sleeps well past however long the test needs to SIGKILL it."""
    checkpoint_writer("stage_1")
    time.sleep(60)
    checkpoint_writer("stage_2")  # never reached in the SIGKILL test


def test_sigkill_mid_job_lands_failed_with_checkpoint(gate_metrics: dict) -> None:
    with session_scope() as session:
        job = job_ops.create_job(session)
        job_id = job.id

    process = sandbox.start_job(job_id, "gate-test-worker", _dummy_job_stage)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with session_scope() as session:
                row = job_ops.get_job(session, job_id)
                if row.checkpoint == {"stage": "stage_1"}:
                    break
            time.sleep(0.1)
        else:
            pytest.fail("child never reached stage_1 checkpoint before timeout")

        assert process.pid is not None
        os.kill(process.pid, signal.SIGKILL)
        process.join(timeout=10)
        assert not process.is_alive(), "child process did not die after SIGKILL"
    finally:
        sandbox.reconcile_after_exit(job_id)

    with session_scope() as session:
        row = job_ops.get_job(session, job_id)
        assert row.status == job_ops.JobStatus.FAILED.value, (
            f"expected FAILED, job landed in {row.status!r}"
        )
        assert row.checkpoint == {"stage": "stage_1"}, (
            f"expected last checkpoint preserved, got {row.checkpoint!r}"
        )

    gate_metrics["sigkill_job_id"] = str(job_id)
    gate_metrics["sigkill_final_status"] = job_ops.JobStatus.FAILED.value
