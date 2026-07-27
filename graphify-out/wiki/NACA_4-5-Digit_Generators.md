# NACA 4/5-Digit Generators

> 18 nodes · cohesion 0.16

## Key Concepts

- **naca.py** (14 connections) — `backend/airfoils/naca.py`
- **airfoil_resolver.py** (10 connections) — `backend/geometry/airfoil_resolver.py`
- **types.py** (9 connections) — `backend/airfoils/types.py`
- **AirfoilFormat** (7 connections) — `backend/airfoils/types.py`
- **_assemble()** (5 connections) — `backend/airfoils/naca.py`
- **_camber4()** (4 connections) — `backend/airfoils/naca.py`
- **_camber5()** (4 connections) — `backend/airfoils/naca.py`
- **_thickness()** (4 connections) — `backend/airfoils/naca.py`
- **ndarray** (4 connections)
- **Enum** (2 connections)
- **NACA half-thickness distribution yt(x) for max thickness fraction t     (open TE** (1 connections) — `backend/airfoils/naca.py`
- **NACA 4- and 5-digit airfoil generators (closed-form).  Produces canonical-order** (1 connections) — `backend/airfoils/naca.py`
- **4-digit camber line yc and slope dyc/dx.** (1 connections) — `backend/airfoils/naca.py`
- **5-digit non-reflex camber line yc and slope dyc/dx.** (1 connections) — `backend/airfoils/naca.py`
- **Combine camber + thickness into canonical TE→upper→LE→lower→TE points.** (1 connections) — `backend/airfoils/naca.py`
- **str** (1 connections)
- **Core airfoil types shared across the P1 subsystem.  Canonical representation (do** (1 connections) — `backend/airfoils/types.py`
- **Resolve a station's airfoil NAME to canonical unit-chord points, reusing the P1** (1 connections) — `backend/geometry/airfoil_resolver.py`

## Relationships

- [Airfoil Metrics & NACA Generation](Airfoil_Metrics_%26_NACA_Generation.md) (8 shared connections)
- [UIUC Airfoil Ingestion](UIUC_Airfoil_Ingestion.md) (6 shared connections)
- [Canonical Airfoil Data Class](Canonical_Airfoil_Data_Class.md) (4 shared connections)
- [Airfoil Resampling Pipeline](Airfoil_Resampling_Pipeline.md) (3 shared connections)
- [OML Loft Construction](OML_Loft_Construction.md) (1 shared connections)
- [Spar Surfaces & Hardpoints](Spar_Surfaces_%26_Hardpoints.md) (1 shared connections)

## Source Files

- `backend/airfoils/naca.py`
- `backend/airfoils/types.py`
- `backend/geometry/airfoil_resolver.py`

## Audit Trail

- EXTRACTED: 70 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*