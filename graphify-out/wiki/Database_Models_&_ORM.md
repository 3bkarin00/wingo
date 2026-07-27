# Database Models & ORM

> 70 nodes · cohesion 0.06

## Key Concepts

- **jobs.py** (16 connections) — `backend/worker/jobs.py`
- **db_models.py** (15 connections) — `backend/schema/db_models.py`
- **sandbox.py** (13 connections) — `backend/worker/sandbox.py`
- **JobRow** (12 connections) — `backend/schema/db_models.py`
- **session_scope()** (12 connections) — `backend/schema/db.py`
- **reaper.py** (11 connections) — `backend/worker/reaper.py`
- **test_p00_foundation.py** (11 connections) — `tests/gates/test_p00_foundation.py`
- **Base** (9 connections) — `backend/schema/db_models.py`
- **heartbeat.py** (7 connections) — `backend/worker/heartbeat.py`
- **UUID** (7 connections)
- **start_job()** (7 connections) — `backend/worker/sandbox.py`
- **get_redis_client()** (6 connections) — `backend/worker/heartbeat.py`
- **Session** (6 connections)
- **reap_orphaned_jobs()** (6 connections) — `backend/worker/reaper.py`
- **_child_entry()** (6 connections) — `backend/worker/sandbox.py`
- **run_job()** (6 connections) — `backend/worker/sandbox.py`
- **conftest.py** (6 connections) — `tests/gates/conftest.py`
- **db.py** (5 connections) — `backend/schema/db.py`
- **UUID** (5 connections)
- **reconcile_after_exit()** (5 connections) — `backend/worker/sandbox.py`
- **GateResultRow** (4 connections) — `backend/schema/db_models.py`
- **heartbeat_alive()** (4 connections) — `backend/worker/heartbeat.py`
- **write_heartbeat()** (4 connections) — `backend/worker/heartbeat.py`
- **create_job()** (4 connections) — `backend/worker/jobs.py`
- **get_job()** (4 connections) — `backend/worker/jobs.py`
- *... and 45 more nodes in this community*

## Relationships

- [Reference Geometry & Config Root](Reference_Geometry_%26_Config_Root.md) (3 shared connections)
- [Wing Config Data Models](Wing_Config_Data_Models.md) (1 shared connections)

## Source Files

- `backend/schema/db.py`
- `backend/schema/db_models.py`
- `backend/worker/heartbeat.py`
- `backend/worker/jobs.py`
- `backend/worker/reaper.py`
- `backend/worker/sandbox.py`
- `migrations/env.py`
- `tests/gates/conftest.py`
- `tests/gates/test_p00_foundation.py`

## Audit Trail

- EXTRACTED: 268 (94%)
- INFERRED: 16 (6%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*