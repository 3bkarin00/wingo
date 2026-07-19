---
title: cadquery/OCP/gmsh ImportError libGL.so.1 / libXcursor.so.1 on a bare workspace
tags: [environment, occ, gmsh, coder-workspace, incident]
source: "docs/known_issues.md (migrated); R0 probes, docs/r0_findings/p00.md"
phase: p00
confidence: verified
last_updated: 2026-07-19
---

`cadquery-ocp` links libGL via OpenCASCADE's visualization toolkit even for
headless boolean/geometry ops with no rendering involved; `gmsh`'s wheel
similarly links X11 cursor/render libs. A bare Ubuntu 24.04 Coder workspace
has neither — pip installs fine, the native `.so` fails to `dlopen` at
import time (`ImportError: libGL.so.1: cannot open shared object file`).

Recurs across workspace restarts (the workspace agent drops apt-installed
native libs). Fix every time, not just once:

```
sudo apt-get update && sudo apt-get install -y \
  libgl1 libglu1-mesa libxrender1 libxext6 libxcursor1 \
  libxinerama1 libxft2 libxrandr2 libxi6
```

`apt-get update` is required first if the mirror has moved on since the
workspace image was built — `apt-get install` alone can 404 on stale
package-index entries otherwise. Verify with `python -c "import cadquery"`
before running anything real. Worth baking into the workspace image/
dotfiles so future rebuilds don't need to rediscover it — not done as of
2026-07-19.
