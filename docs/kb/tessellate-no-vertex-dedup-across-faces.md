---
title: "cq.Shape.tessellate() doesn't dedupe vertices across face boundaries — naive edge-count manifold checks false-fail on real watertight solids"
tags: [occ, tessellation, stl, export, gate-bug]
source: "P9 export gate development (tests/gates/test_p09_export.py), 2026-07-19 session"
phase: p09
confidence: verified
last_updated: 2026-07-19
---

`cq.Shape.tessellate(tol)` concatenates each FACE's own local
`BRepMesh_IncrementalMesh` triangulation into one global (vertices,
triangles) pair WITHOUT merging coincident vertices at shared face
boundaries — two adjacent faces' triangulations each get their OWN vertex
index for the same 3D point on their shared edge.

A naive manifold check ("every edge, identified by its vertex-INDEX pair,
must appear in exactly 2 triangles") therefore sees every shared-face-
boundary edge as TWO DIFFERENT edges, each used only once — a false
non-manifold failure, even on a solid a DIFFERENT gate already proves
watertight via `BRepCheck_Analyzer` (found on `te_half.yaml`'s `wing` body
while building the P9 export gate's "STL manifold per body" check).

Fix: snap-merge tessellation vertices by ROUNDED POSITION (not index)
before building the edge-adjacency map — round to 1e-4mm (tighter than
`TESSELLATION_TOLERANCE_MM` so genuinely distinct nearby vertices never
wrongly merge; loose enough to catch the exactly/near-coincident ones OCC's
per-face tessellation actually produces at a shared edge). General lesson:
a `(vertices, triangles)` pair from a multi-face tessellation is a set of
independently-triangulated DISKS, not a pre-merged mesh graph — any
topology check across face boundaries needs a position-based merge step
first, the same trap-shape as the π-joint bond-gap verification saga (see
pi-joint-design-rules.md) where re-deriving a fact from finished 3D
geometry encoded a wrong topological assumption twice before the right,
simpler check was found.
