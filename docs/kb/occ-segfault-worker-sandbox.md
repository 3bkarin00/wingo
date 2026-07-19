---
title: "F2 — OCC failures are often segfaults, not exceptions; run jobs in a monitored subprocess"
tags: [occ, worker, sandbox, reliability, f2]
source: "plan.md §10 F2, §4 architecture; backend/worker/sandbox.py, heartbeat.py, reaper.py"
phase: p00
confidence: verified
last_updated: 2026-07-19
---

A malformed or pathological OCC operation can SIGSEGV the process instead of
raising a Python exception — a `try/except` around the geometry call catches
nothing because the interpreter is gone. Mitigation is architectural, not a
try/except: every job runs in a CHILD PROCESS the parent explicitly
monitors (`backend/worker/sandbox.py`), not just awaits.

- `multiprocessing.get_context("spawn")` (not `"fork"`) — the child gets a
  fresh interpreter and opens its own DB/Redis connections rather than
  inheriting the parent's already-initialized connection pool across a
  fork (a fork-after-connection-pool-init hazard, independent of the OCC
  segfault risk itself).
- `start_job`/`run_job` mark the job RUNNING, start the child, and on any
  exit (however it exited — including a bare SIGKILL) `reconcile_after_exit`
  guarantees the job is never left RUNNING with nothing actually running
  it: if the child died before setting its own terminal status, it's marked
  FAILED, preserving whatever checkpoint was last written.
- `heartbeat.py` (Redis, TTL'd key) + `reaper.py` (fails RUNNING jobs whose
  heartbeat expired) are belt-and-suspenders for the case `sandbox.
  reconcile_after_exit` can't cover: the PARENT dying too, not just the
  child, so nothing ever calls reconcile.
- P0's own gate SIGKILLs a worker subprocess mid-job and asserts the job
  lands in FAILED with a checkpoint, not RUNNING — the ONLY way to actually
  verify this contract, since a normal test can't "trust" it without
  triggering the real failure mode.
