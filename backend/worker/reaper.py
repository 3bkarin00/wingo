"""Reaper: fails RUNNING jobs whose Redis heartbeat has expired.

Belt-and-suspenders for the case `sandbox.reconcile_after_exit` can't cover
— the PARENT process dying too, not just the child (so nothing ever calls
reconcile). Meant to be invoked periodically by a scheduler or at worker
startup, independent of any single job's own process tree.
"""
import uuid

from backend.schema.db import session_scope
from backend.schema.db_models import JobRow
from backend.worker import jobs as job_ops
from backend.worker.heartbeat import get_redis_client, heartbeat_alive


def reap_orphaned_jobs() -> list[uuid.UUID]:
    reaped: list[uuid.UUID] = []
    redis_client = get_redis_client()
    with session_scope() as session:
        running_jobs = (
            session.query(JobRow)
            .filter(JobRow.status == job_ops.JobStatus.RUNNING.value)
            .all()
        )
        for job in running_jobs:
            if not heartbeat_alive(redis_client, job.id):
                job_ops.set_failed(session, job.id)
                reaped.append(job.id)
    return reaped
