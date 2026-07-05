"""Redis heartbeat: the child process refreshes a TTL'd key while it's
alive. `reaper.py` uses expiry (not the DB row) to detect a job whose worker
process is truly gone, including the case where the PARENT died too (so
`sandbox.reconcile_after_exit` never got a chance to run)."""
import os
import time

import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

DEFAULT_TTL_SECONDS = 10


def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL)


def write_heartbeat(client: redis.Redis, job_id, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    client.set(f"heartbeat:{job_id}", str(time.time()), ex=ttl_seconds)


def heartbeat_alive(client: redis.Redis, job_id) -> bool:
    return bool(client.exists(f"heartbeat:{job_id}"))
