---
title: "Test-only geometry build cache: config-hash + source-hash keys; construction cached, assertions NEVER"
tags: [testing, performance, gates, cache]
source: "tests/gates/geometry_cache.py"
phase: p04
confidence: verified
last_updated: 2026-07-19
---

`tests/gates/geometry_cache.py` exists because full gate runs were being
used as the diagnostic loop for construction questions (~minutes per
hypothesis) — real pain, solved by disk-caching expensive boolean
CONSTRUCTION output, never anything downstream of it.

- Cache key = `SHA256(config.model_dump_json() + concatenated source bytes
  of every geometry module the construction depends on)`. Changing either
  gives a different key — there is no manual invalidation step and no
  staleness risk by construction; a stale entry just becomes unreachable,
  never silently wrong.
- Only the RAW, pre-shard-filter boolean output is cached (verified
  round-trip-safe via `cq.Shape.exportBrep`/`importBrep` for both single-
  and multi-solid shapes, `probe_brep_cache.py`). Every downstream
  computation — `filter_shards`, sort, volume, watertightness, tangency,
  clearance — ALWAYS runs fresh against the loaded shapes, cache hit or
  miss. Caching can only ever skip the boolean; it can never skip an
  assertion.
- **PRODUCTION/WORKER CODE NEVER USES THIS** (CLAUDE.md hard rule) — it
  imports `backend/pipeline.py`'s uncached build path, always builds fresh.
  This is test-only performance infrastructure, full stop.
- Multiple gate files can DELIBERATELY share one cache entry by using
  IDENTICAL `SOURCE_FILES`/shape-name lists/config content (e.g.
  `test_p06_ext_interlock.py` reuses `test_p06_sandwich.py`'s sandwich-body
  cache) — whichever gate runs first in a session pays the real cost once,
  the other hits the cache in milliseconds.
- Lives beside `conftest.py` (not at `tests/` root) because `tests/` has no
  `__init__.py` anywhere — pytest's rootless import mode puts each test
  directory on `sys.path` independently, so `from geometry_cache import
  ...` resolves the same way `conftest.py`'s own fixtures do.
