# Watertightness Gate Tests

> 6 nodes · cohesion 0.33

## Key Concepts

- **is_watertight()** (12 connections) — `backend/geometry/loft.py`
- **test_fresh_build_matches_gate_criteria()** (3 connections) — `tests/gates/test_p04_te_cut.py`
- **Solid** (2 connections)
- **test_exactly_two_watertight_bodies()** (2 connections) — `tests/gates/test_p04_te_cut.py`
- **Watertight = OCC-valid AND every shell is closed (r0_findings/p02.md).** (1 connections) — `backend/geometry/loft.py`
- **Slow tier: force one real, uncached rebuild per config (bypassing the     cache** (1 connections) — `tests/gates/test_p04_te_cut.py`

## Relationships

- [OML Loft Construction](OML_Loft_Construction.md) (5 shared connections)
- [Hinge Frame & Viewer Export](Hinge_Frame_%26_Viewer_Export.md) (3 shared connections)
- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (3 shared connections)

## Source Files

- `backend/geometry/loft.py`
- `tests/gates/test_p04_te_cut.py`

## Audit Trail

- EXTRACTED: 21 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*