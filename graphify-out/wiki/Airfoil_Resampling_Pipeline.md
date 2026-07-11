# Airfoil Resampling Pipeline

> 24 nodes · cohesion 0.14

## Key Concepts

- **reference.py** (25 connections) — `backend/geometry/reference.py`
- **derive_hinge_axis()** (14 connections) — `backend/geometry/reference.py`
- **cosine_resample()** (11 connections) — `backend/airfoils/resample.py`
- **resample.py** (10 connections) — `backend/airfoils/resample.py`
- **close_blunt_te()** (7 connections) — `backend/airfoils/resample.py`
- **interp_surface()** (7 connections) — `backend/airfoils/resample.py`
- **split_surfaces()** (7 connections) — `backend/airfoils/resample.py`
- **_get_canonical_points_at_xc()** (7 connections) — `backend/geometry/reference.py`
- **cosine_x()** (6 connections) — `backend/airfoils/resample.py`
- **_equidistant_z_canonical()** (6 connections) — `backend/geometry/reference.py`
- **ndarray** (5 connections)
- **ndarray** (4 connections)
- **_nearest_dist_to_polyline()** (3 connections) — `backend/geometry/reference.py`
- **Cosine resampling + blunt-TE closure — the shared final stage every airfoil pass** (1 connections) — `backend/airfoils/resample.py`
- **Split canonical points (TE→upper→LE→lower→TE) into upper and lower     surfaces,** (1 connections) — `backend/airfoils/resample.py`
- **Interpolate a surface's y at target_x. Guards np.interp's requirement     of str** (1 connections) — `backend/airfoils/resample.py`
- **n_per_surface cosine-spaced x-stations LE(0)→TE(1); clusters points     near bot** (1 connections) — `backend/airfoils/resample.py`
- **Resample a canonical airfoil to exactly n_total points (must be odd)     with co** (1 connections) — `backend/airfoils/resample.py`
- **Ensure the TE gap is at least te_thickness_frac (unit chord), by adding     a li** (1 connections) — `backend/airfoils/resample.py`
- **Reference geometry (plan.md §8.4).  Builds spar ruled surfaces, rib planes (auto** (1 connections) — `backend/geometry/reference.py`
- **Derived-axis-height hinge line (ADR-003). hinge_xc stays the user     parameter** (1 connections) — `backend/geometry/reference.py`
- **Return (upper_z, lower_z, camber_z) at chord fraction xc.** (1 connections) — `backend/geometry/reference.py`
- **Min distance from a 2D point to a 2D polyline, via vectorized     point-to-segme** (1 connections) — `backend/geometry/reference.py`
- **The z (canonical unit-chord space) on the vertical line x=xc where     distance** (1 connections) — `backend/geometry/reference.py`

## Relationships

- [Spar Surfaces & Hardpoints](Spar_Surfaces_%26_Hardpoints.md) (12 shared connections)
- [Reference Geometry & Config Root](Reference_Geometry_%26_Config_Root.md) (6 shared connections)
- [UIUC Airfoil Ingestion](UIUC_Airfoil_Ingestion.md) (5 shared connections)
- [Airfoil Metrics & NACA Generation](Airfoil_Metrics_%26_NACA_Generation.md) (4 shared connections)
- [NACA 4/5-Digit Generators](NACA_4-5-Digit_Generators.md) (3 shared connections)
- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (3 shared connections)
- [Canonical Airfoil Data Class](Canonical_Airfoil_Data_Class.md) (2 shared connections)
- [Hinge Axis Construction & R0 Probe](Hinge_Axis_Construction_%26_R0_Probe.md) (2 shared connections)
- [Geometry Module & ADR Map](Geometry_Module_%26_ADR_Map.md) (2 shared connections)
- [OML Loft Construction](OML_Loft_Construction.md) (1 shared connections)
- [Wing Config Data Models](Wing_Config_Data_Models.md) (1 shared connections)
- [TE Surface Cut Construction](TE_Surface_Cut_Construction.md) (1 shared connections)

## Source Files

- `backend/airfoils/resample.py`
- `backend/geometry/reference.py`

## Audit Trail

- EXTRACTED: 122 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*