"""Disk cache for expensive OCC boolean-construction outputs — TEST-ONLY
performance infrastructure (production/worker code always builds fresh; see
backend/geometry/te_cut.py's own build_te_cut_shapes/finish_te_cut split).
Full gate runs were being used as the diagnostic loop for construction
questions (~minutes per hypothesis, every time) — this exists so a gate
re-run against an unchanged config and unchanged geometry code loads its
expensive boolean output in milliseconds instead of rebuilding it.

Cache key = SHA256(config's own canonical JSON + the concatenated source of
every geometry module the construction depends on). Changing EITHER gives a
different key, so a stale entry can never be read back against new
code/config — there is no manual invalidation step and no staleness risk by
construction (an old entry just becomes unreachable, never silently wrong).

Only the raw, pre-shard-filter boolean output shapes are cached — verified
round-trip-safe for both single- and multi-solid shapes via cq.Shape's own
exportBrep/importBrep (docs/r0_findings/p04.md, probe_brep_cache.py). Every
downstream computation — filter_shards, sort, volume, watertightness,
tangency, clearance — always runs fresh against the loaded shapes, cache hit
or miss, so caching can only ever skip the boolean; it can never skip an
assertion.

Lives beside conftest.py (not at the tests/ root) because tests/ has no
__init__.py anywhere — pytest's rootless import mode puts each test
directory on sys.path independently, so a sibling-module import
(`from geometry_cache import ...`) resolves the same way conftest.py's
fixtures already do for every file in tests/gates/. If a later phase needs
this from tests/golden/ or tests/oracle/ too, promote it to a real tests/
package at that point rather than duplicating it.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

import cadquery as cq

from backend.schema.models import Config

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_ROOT = REPO_ROOT / "artifacts" / "cache"


def _source_digest(source_files: list[str]) -> bytes:
    h = hashlib.sha256()
    for rel in sorted(source_files):
        h.update(rel.encode())
        h.update((REPO_ROOT / rel).read_bytes())
    return h.digest()


def cache_key(config: Config, source_files: list[str]) -> str:
    """Stable across runs for the same config VALUES (pydantic's
    model_dump_json is field-order-deterministic, not insertion-order) and
    the same file CONTENTS (content hash, not mtime — a no-op touch doesn't
    bust the cache, but any real edit, including whitespace, does)."""
    h = hashlib.sha256()
    h.update(config.model_dump_json().encode())
    h.update(_source_digest(source_files))
    return h.hexdigest()[:32]


def get_or_build_shapes(
    config: Config,
    source_files: list[str],
    shape_names: list[str],
    build_fn: Callable[[], list[cq.Shape]],
    cache_root: Path = CACHE_ROOT,
    force_fresh: bool = False,
) -> tuple[list[cq.Shape], bool]:
    """Returns (shapes, was_cache_hit) for `shape_names`, in order. `build_fn`
    is called ONLY on a miss (or when force_fresh=True, e.g. the slow tier
    proving the cache still matches a real build) and must return the RAW
    shapes before any pass/fail judgment (e.g. pre-shard-filter Compounds) —
    a judgment (shard filtering, pass/fail) must never be what gets cached.
    A fresh build always (re)writes the cache, so a slow-tier forced build
    also warms it for the next fast-tier run."""
    key = cache_key(config, source_files)
    cache_dir = cache_root / key
    paths = [cache_dir / f"{name}.brep" for name in shape_names]

    if not force_fresh and all(p.exists() for p in paths):
        return [cq.Shape.importBrep(str(p)) for p in paths], True

    shapes = build_fn()
    assert len(shapes) == len(shape_names), (
        f"build_fn returned {len(shapes)} shape(s), expected {len(shape_names)} ({shape_names})"
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    for shape, path in zip(shapes, paths):
        tmp = path.with_suffix(".brep.tmp")
        shape.exportBrep(str(tmp))
        tmp.rename(path)  # rename only after a complete write -> no torn cache entries
    return shapes, False
