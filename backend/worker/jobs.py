"""Job status/checkpoint operations against the `jobs` table (§7)."""
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.orm import Session

from backend.schema.db_models import JobRow


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


def create_job(session: Session, config_id: uuid.UUID | None = None) -> JobRow:
    job = JobRow(status=JobStatus.PENDING.value, config_id=config_id)
    session.add(job)
    session.flush()
    return job


def set_running(session: Session, job_id: uuid.UUID, worker_id: str) -> None:
    job = session.get(JobRow, job_id)
    job.status = JobStatus.RUNNING.value
    job.worker_id = worker_id
    job.started_at = datetime.now(timezone.utc)
    session.flush()


def set_checkpoint(session: Session, job_id: uuid.UUID, checkpoint: dict) -> None:
    job = session.get(JobRow, job_id)
    job.checkpoint = checkpoint
    session.flush()


def set_done(session: Session, job_id: uuid.UUID) -> None:
    job = session.get(JobRow, job_id)
    job.status = JobStatus.DONE.value
    session.flush()


def set_failed(session: Session, job_id: uuid.UUID, checkpoint: dict | None = None) -> None:
    job = session.get(JobRow, job_id)
    job.status = JobStatus.FAILED.value
    if checkpoint is not None:
        job.checkpoint = checkpoint
    session.flush()


def get_job(session: Session, job_id: uuid.UUID) -> JobRow | None:
    return session.get(JobRow, job_id)
