"""Subprocess sandbox for geometry-worker jobs (F2: OCC failures are often
segfaults, not exceptions).

A job runs in a child process the parent explicitly monitors rather than
just awaiting an exception. If the child dies abnormally — killed by a
signal, e.g. the SIGKILL a real segfault would deliver — the parent detects
this via `reconcile_after_exit` and marks the job FAILED at its last
checkpoint, never leaving it RUNNING.

Uses the 'spawn' start method (not 'fork'): the child gets a fresh
interpreter and opens its own DB/Redis connections rather than inheriting
the parent's already-initialized connection pool across a fork.
"""
import multiprocessing as mp
import uuid
from collections.abc import Callable

from backend.schema.db import session_scope
from backend.worker import jobs as job_ops
from backend.worker.heartbeat import get_redis_client, write_heartbeat

_CTX = mp.get_context("spawn")


def _child_entry(job_id: uuid.UUID, target: Callable, args: tuple) -> None:
    redis_client = get_redis_client()

    def checkpoint_writer(stage: str) -> None:
        with session_scope() as session:
            job_ops.set_checkpoint(session, job_id, {"stage": stage})
        write_heartbeat(redis_client, job_id)

    write_heartbeat(redis_client, job_id)
    try:
        target(job_id, checkpoint_writer, *args)
    except Exception:
        with session_scope() as session:
            job_ops.set_failed(session, job_id)
        raise
    else:
        with session_scope() as session:
            job_ops.set_done(session, job_id)


def start_job(
    job_id: uuid.UUID, worker_id: str, target: Callable, *args
) -> mp.process.BaseProcess:
    """Marks the job RUNNING and starts its child process. Does not block —
    callers that need adversarial control (e.g. killing the child mid-job)
    call this, act on the returned process, then call
    `reconcile_after_exit`."""
    with session_scope() as session:
        job_ops.set_running(session, job_id, worker_id)

    process = _CTX.Process(target=_child_entry, args=(job_id, target, args))
    process.start()
    return process


def reconcile_after_exit(job_id: uuid.UUID) -> None:
    """Call once the child process has exited, however it exited. Guarantees
    the job is never left RUNNING when nothing is running it: if the child
    died before setting a terminal status itself, this marks it FAILED,
    preserving whatever checkpoint was last written."""
    with session_scope() as session:
        row = job_ops.get_job(session, job_id)
        if row is not None and row.status == job_ops.JobStatus.RUNNING.value:
            job_ops.set_failed(session, job_id)


def run_job(
    job_id: uuid.UUID, worker_id: str, target: Callable, *args
) -> mp.process.BaseProcess:
    """Convenience wrapper for the normal (non-adversarial) path: start,
    block until done, reconcile."""
    process = start_job(job_id, worker_id, target, *args)
    process.join()
    reconcile_after_exit(job_id)
    return process
