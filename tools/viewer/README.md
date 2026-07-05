# Backend capability viewer (dev diagnostic — not the product UI)

A throwaway 3D viewer to see what the geometry pipeline can actually build
right now (P2 OML loft + P3 reference geometry). The real product UI is
React + three.js against the live API, built in P10 (plan.md §9) — this tool
exists only so a phase's output is visible without waiting for that.

## Regenerate

1. On the `wingo.coder` workspace (cadquery/OCP only exist there):
   ```
   .venv/bin/python scripts/export_viewer_data.py tests/configs/edge/devices_full.yaml
   ```
   rsync `artifacts/viewer_data.json` back to this Mac.
2. Locally (pure stdlib, no cadquery needed):
   ```
   python3 tools/viewer/build.py
   ```
   Writes `tools/viewer/dist/viewer.html` — open it directly in a browser.

## Layout

- `index_template.html` — page shell (CSS + markup), with 3 splice points.
- `app.js` — scene setup, hand-rolled orbit camera (drag/wheel), layer
  toggles built from whatever the exported data actually contains (spar
  names, hinge axes, hardpoints all vary by config).
- `build.py` — assembles the final self-contained HTML: template + vendored
  three.js (cached in `.cache/`, fetched once from jsdelivr) + the exported
  JSON + `app.js`. No external requests at view time.
- `.cache/`, `dist/` — gitignored (vendored lib + generated, config-specific
  output; not source).
