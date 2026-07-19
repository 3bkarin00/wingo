---
title: "Swept caps/preforms use sampled frames + explicit per-point normals + loft, not a true sweep API"
tags: [occ, sweep, spars, pi-joints, d23, d24]
source: "backend/geometry/spars.py; backend/tolerances.py SPAR_CAP_SWEEP_FRAMES; docs/r0_findings/p06_ext.md probe_sweep_spine.py"
phase: p06
confidence: verified
last_updated: 2026-07-19
---

`c_channel`/`i_beam`/`box` spar caps (D23) and π-joint preform bodies (D24)
are NOT built with a CadQuery/OCP "sweep a profile along a spine" API.
Instead: sample N frames along the path (`SPAR_CAP_SWEEP_FRAMES = 30`),
place the 2D profile at each frame using an EXPLICIT locally-computed
normal (the cavity surface normal at that point, not a Frenet frame derived
from the curve's own curvature/torsion), then loft the stack of placed
profiles.

Why not a real sweep: a Frenet-frame-based sweep can twist/drift
unexpectedly wherever the path's curvature briefly drops near zero (a
well-known sweep-orientation instability) — using the SURFACE's own local
normal instead of a curve-derived frame sidesteps that failure mode
entirely, at the cost of needing enough sample frames for the loft to
reproduce the true swept volume.

R0-verified (`probe_sweep_spine.py`, docs/r0_findings/p06_ext.md): the
sampled-frame+loft technique reproduces the analytic swept volume within
0.06% at 30 frames on a deliberately curved+twisted synthetic spine — 30 is
not an arbitrary round number, it's the frame count that cleared that
bar. `CAP_PATH_END_TRIM_FRAC` (2%) trims the near-vertical root/tip closure
segments off each end of the spar-surface∩cavity section loop before
splitting it into upper/lower cap-path chains, since those belong to
neither chain.
