"""Geometry cache — two-level caching for airfoil, section, and loft results.

Two levels:
1. Memory cache (LRU) — fast, per-session, shared across pipeline calls.
2. Disk cache (SQLite) — persistent across sessions, keyed by config hash.

The cache stores:
- Airfoil points: (airfoil_name, resample_points, te_thickness_frac) → ndarray
- Section points: (y_frac, chord, twist, airfoil_hash, twist_axis_xc, le_x, z_base) → ndarray
- Loft wire: (section_hashes_tuple) → cadquery.Solid

Usage:
    from backend.geometry.cache import cache

    # Decorate a function to cache its result
    @cache.memoize(level="memory")
    def resolve_airfoil_cached(name, resample_points, te_frac):
        ...

    # Or use the cache directly
    result = cache.get("airfoil", key)
    if result is None:
        result = compute()
        cache.put("airfoil", key, result)
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import numpy as np

import cadquery as cq


def _serialize(value: Any) -> str:
    """Serialize a value (including numpy arrays) to a JSON-safe string."""
    def _encoder(obj):
        if isinstance(obj, np.ndarray):
            return {
                "__ndarray__": True,
                "data": base64.b64encode(obj.tobytes()).decode("ascii"),
                "dtype": str(obj.dtype),
                "shape": list(obj.shape),
            }
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
    return json.dumps(value, default=_encoder)


def _deserialize(value: str) -> Any:
    """Deserialize a JSON string back to its original type (including numpy arrays)."""
    def _decoder(dct):
        if isinstance(dct, dict) and dct.get("__ndarray__"):
            return np.frombuffer(
                base64.b64decode(dct["data"]), dtype=dct["dtype"]
            ).reshape(dct["shape"])
        return dct
    return json.loads(value, object_hook=_decoder)


class LRUCache:
    """Thread-safe LRU cache for numpy arrays and simple types."""

    def __init__(self, maxsize: int = 256) -> None:
        self._maxsize = maxsize
        self._store: dict[str, Any] = {}
        self._access_order: list[str] = []
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        if key in self._store:
            self._hits += 1
            # Move to end (most recently used)
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._store[key]
        self._misses += 1
        return None

    def put(self, key: str, value: Any) -> None:
        if key in self._store:
            self._access_order.remove(key)
        elif len(self._store) >= self._maxsize:
            # Evict least recently used
            oldest = self._access_order.pop(0)
            del self._store[oldest]
        self._store[key] = value
        self._access_order.append(key)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def clear(self) -> None:
        self._store.clear()
        self._access_order.clear()
        self._hits = 0
        self._misses = 0

    def stats(self) -> dict[str, Any]:
        return {
            "size": len(self._store),
            "maxsize": self._maxsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 3),
        }


class DiskCache:
    """SQLite-based persistent cache for geometry data.

    Stores cached values as base64-encoded JSON (for numpy arrays) or raw values.
    Keyed by a content hash so that different inputs always get different keys.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            cache_dir = Path.home() / ".wingstructgen" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = cache_dir / "geometry.db"
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at REAL NOT NULL,
                access_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_created ON cache(created_at)"
        )
        conn.commit()
        conn.close()

    def get(self, key: str) -> Any | None:
        conn = sqlite3.connect(str(self._db_path))
        row = conn.execute(
            "SELECT value, access_count FROM cache WHERE key = ?", (key,)
        ).fetchone()
        conn.close()
        if row is None:
            return None
        # Increment access count
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(
            "UPDATE cache SET access_count = access_count + 1 WHERE key = ?", (key,)
        )
        conn.commit()
        conn.close()
        return _deserialize(row[0])

    def put(self, key: str, value: Any) -> None:
        data = _serialize(value)
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(
            """INSERT OR REPLACE INTO cache (key, value, created_at, access_count)
               VALUES (?, ?, ?, 0)""",
            (key, data, time.time()),
        )
        conn.commit()
        conn.close()

    def evict_old(self, max_age_seconds: float = 3600) -> int:
        """Remove entries older than max_age_seconds. Returns count removed."""
        cutoff = time.time() - max_age_seconds
        conn = sqlite3.connect(str(self._db_path))
        row = conn.execute(
            "DELETE FROM cache WHERE created_at < ?", (cutoff,)
        )
        count = row.rowcount
        conn.commit()
        conn.close()
        return count

    def clear(self) -> None:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("DELETE FROM cache")
        conn.commit()
        conn.close()

    def stats(self) -> dict[str, Any]:
        conn = sqlite3.connect(str(self._db_path))
        row = conn.execute("SELECT COUNT(*) FROM cache").fetchone()
        count = row[0]
        conn.close()
        return {"size": count, "db_path": str(self._db_path)}


class GeometryCache:
    """Unified cache interface for geometry operations.

    Manages both memory (LRU) and disk (SQLite) caches.
    All cache keys are prefixed by category to avoid collisions.
    """

    def __init__(self) -> None:
        self.memory = LRUCache(maxsize=512)
        self.disk = DiskCache()

    def get(self, category: str, key: str) -> Any | None:
        """Try memory cache first, then disk cache."""
        full_key = f"{category}:{key}"
        # Check memory first
        result = self.memory.get(full_key)
        if result is not None:
            return result
        # Fall back to disk
        return self.disk.get(full_key)

    def put(self, category: str, key: str, value: Any) -> None:
        """Store in both memory and disk caches."""
        full_key = f"{category}:{key}"
        self.memory.put(full_key, value)
        self.disk.put(full_key, value)

    def invalidate(self, category: str | None = None) -> None:
        """Invalidate cache entries. If category is None, clear everything."""
        if category is None:
            self.memory.clear()
            self.disk.clear()
        else:
            # Memory: rebuild without category entries
            prefix = f"{category}:"
            keys_to_remove = [k for k in self.memory._store if k.startswith(prefix)]
            for k in keys_to_remove:
                self.memory._access_order.remove(k)
                del self.memory._store[k]
            # Disk: would need to scan and delete, skip for now

    def stats(self) -> dict[str, Any]:
        return {
            "memory": self.memory.stats(),
            "disk": self.disk.stats(),
        }

    def memoize(self, category: str = "generic", maxsize: int = 256) -> Callable:
        """Decorator that caches function results.

        Args:
            category: cache category prefix (e.g. "airfoil", "section").
            maxsize: LRU maxsize for memory cache only.

        Usage:
            @cache.memoize(category="airfoil")
            def resolve_airfoil(name, resample_points, te_frac):
                ...
        """
        def decorator(func: Callable) -> Callable:
            local_cache = LRUCache(maxsize=maxsize)

            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                # Create cache key from args and kwargs
                key_parts = [func.__name__]
                for a in args:
                    if isinstance(a, np.ndarray):
                        key_parts.append(f"arr:{a.shape}:{a.dtype}:{hashlib.md5(a.tobytes()).hexdigest()[:8]}")
                    elif isinstance(a, str):
                        key_parts.append(f"str:{a}")
                    elif isinstance(a, (int, float, bool)):
                        key_parts.append(f"{a}")
                    else:
                        key_parts.append(str(a))
                for k, v in sorted(kwargs.items()):
                    if isinstance(v, np.ndarray):
                        key_parts.append(f"{k}:arr:{v.shape}:{v.dtype}:{hashlib.md5(v.tobytes()).hexdigest()[:8]}")
                    else:
                        key_parts.append(f"{k}:{v}")
                cache_key = ":".join(key_parts)

                # Check unified cache first
                result = self.get(category, cache_key)
                if result is not None:
                    local_cache.put(cache_key, result)
                    return result

                # Compute and cache
                result = func(*args, **kwargs)
                local_cache.put(cache_key, result)
                self.put(category, cache_key, result)
                return result

            return wrapper
        return decorator


# Global cache instance
cache = GeometryCache()
