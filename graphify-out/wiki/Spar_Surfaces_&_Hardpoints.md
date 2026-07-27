# Spar Surfaces & Hardpoints

> 19 nodes · cohesion 0.15

## Key Concepts

- **sections.py** (22 connections) — `backend/geometry/sections.py`
- **build_spar_surfaces()** (11 connections) — `backend/geometry/reference.py`
- **place_section()** (10 connections) — `backend/geometry/sections.py`
- **build_hardpoints()** (9 connections) — `backend/geometry/reference.py`
- **interp_station()** (9 connections) — `backend/geometry/sections.py`
- **le_and_z_offset()** (9 connections) — `backend/geometry/sections.py`
- **_segment_bounds()** (5 connections) — `backend/geometry/sections.py`
- **unit_chord_area()** (4 connections) — `backend/geometry/sections.py`
- **Vector** (3 connections)
- **ndarray** (2 connections)
- **Build a ruled surface shell for each spar from root to tip.** (1 connections) — `backend/geometry/reference.py`
- **Fuselage attachment hardpoints.** (1 connections) — `backend/geometry/reference.py`
- **Section construction & placement (plan.md §8.2).  Each spanwise section = a cano** (1 connections) — `backend/geometry/sections.py`
- **Enclosed area of a closed unit-chord airfoil (shoelace) — the section     area c** (1 connections) — `backend/geometry/sections.py`
- **Scale → twist about (twist_axis_xc·chord, chord line) → place at     (le_x, y, z** (1 connections) — `backend/geometry/sections.py`
- **(start_frac, end_frac, sweep_le_deg, dihedral_deg) per segment.** (1 connections) — `backend/geometry/sections.py`
- **Accumulate LE sweep (X) and dihedral (Z) offsets up to y_frac, honoring     per-** (1 connections) — `backend/geometry/sections.py`
- **Interpolate chord, twist, and airfoil shape at y_frac between the two     bracke** (1 connections) — `backend/geometry/sections.py`
- **Shell** (1 connections)

## Relationships

- [Airfoil Resampling Pipeline](Airfoil_Resampling_Pipeline.md) (12 shared connections)
- [OML Loft Construction](OML_Loft_Construction.md) (12 shared connections)
- [Reference Geometry & Config Root](Reference_Geometry_%26_Config_Root.md) (9 shared connections)
- [Canonical Airfoil Data Class](Canonical_Airfoil_Data_Class.md) (2 shared connections)
- [NACA 4/5-Digit Generators](NACA_4-5-Digit_Generators.md) (1 shared connections)
- [Cove/Nose Arc Profile Construction](Cove-Nose_Arc_Profile_Construction.md) (1 shared connections)
- [False Spar Closing Wall](False_Spar_Closing_Wall.md) (1 shared connections)
- [Sandwich IML Boolean Construction](Sandwich_IML_Boolean_Construction.md) (1 shared connections)
- [Wing Config Data Models](Wing_Config_Data_Models.md) (1 shared connections)
- [TE Surface Cut Construction](TE_Surface_Cut_Construction.md) (1 shared connections)
- [Hinge Frame & Viewer Export](Hinge_Frame_%26_Viewer_Export.md) (1 shared connections)
- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (1 shared connections)

## Source Files

- `backend/geometry/reference.py`
- `backend/geometry/sections.py`

## Audit Trail

- EXTRACTED: 93 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*