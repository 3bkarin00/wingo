# Known Issues — OCC/Gmsh/ezdxf workaround knowledge base

Every resolved kernel fight gets an entry here. Format:

```
## <symptom, short>
- Root cause: ...
- Workaround: ...
- Phase found: pXX
```

Compounds in value toward P15–P16 (molds — the hardest OCC work). Skim the
entries relevant to a phase's libraries before starting that phase's
implementation (session protocol, CLAUDE.md).

## OCP/gmsh ImportError: libGL.so.1 / libXcursor.so.1 missing

- Root cause: `cadquery-ocp` links against libGL (via OpenCASCADE's
  visualization toolkit, even for headless boolean/geometry ops with no
  rendering involved); `gmsh`'s wheel similarly links X11 cursor/render
  libs. A bare Ubuntu 24.04 container/workspace has neither — pip installs
  the Python packages fine, but the native `.so` fails to `dlopen` at import
  time.
- Workaround: `sudo apt-get install -y libgl1 libglu1-mesa libxrender1
  libxext6 libxcursor1 libxinerama1 libxft2 libxrandr2 libxi6` on the
  workspace before running anything that imports `cadquery`/`OCP`/`gmsh`.
  Consider baking this into the Coder workspace image/dotfiles so future
  workspace rebuilds don't need to rediscover it.
- Phase found: p00 (R0 probes, `docs/r0_findings/p00.md`).

## Unmatched shell glob reaches pytest as a literal path

- Root cause: a glob pattern (e.g. `tests/gates/test_p00_*.py`) passed to
  `subprocess.run([pytest, pattern])` is NOT shell-expanded — pytest receives
  the literal string with the `*` in it and exits 2 ("file or directory not
  found"). The Makefile `gate` target worked only because make runs the
  pattern through a shell that expands it; `scripts/run_regress.py` used
  subprocess with no shell, so the same pattern failed.
- Workaround: always expand gate-file globs in Python (`Path.glob`) before
  handing concrete paths to pytest, and guard with an existence check — if a
  phase is marked passed in state.json but no gate file matches, fail loudly
  rather than let an empty/literal glob leak through and masquerade as a pass.
- Phase found: p00 (`scripts/run_regress.py`).
