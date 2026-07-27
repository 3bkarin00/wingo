# Cove/Nose Arc Profile Construction

> 20 nodes · cohesion 0.18

## Key Concepts

- **cove_profile.py** (17 connections) — `backend/geometry/cove_profile.py`
- **build_nose_arc_points()** (16 connections) — `backend/geometry/cove_profile.py`
- **build_station_profiles()** (13 connections) — `backend/geometry/te_cut.py`
- **build_cove_arc_points()** (9 connections) — `backend/geometry/cove_profile.py`
- **find_station_feet()** (8 connections) — `backend/geometry/cove_profile.py`
- **StationFeet** (8 connections) — `backend/geometry/cove_profile.py`
- **ndarray** (7 connections)
- **_forward_sweep_angles()** (5 connections) — `backend/geometry/cove_profile.py`
- **_overlap_extension_rad()** (4 connections) — `backend/geometry/cove_profile.py`
- **_to_3d()** (4 connections) — `backend/geometry/cove_profile.py`
- **.R()** (2 connections) — `backend/geometry/cove_profile.py`
- **Per-station cove/nose SINGLE-arc construction (§8.5, refined — docs/decisions/AD** (1 connections) — `backend/geometry/cove_profile.py`
- **Normal feet of C on the upper (u>0 side) and lower (u<0 side) skin     curves wi** (1 connections) — `backend/geometry/cove_profile.py`
- **Angles from angle_l to angle_u sweeping through the FORWARD side (±π,     i.e. -** (1 connections) — `backend/geometry/cove_profile.py`
- **Anti-unporting angular overlap (ADR-003 addendum A): the nose arc     must not s** (1 connections) — `backend/geometry/cove_profile.py`
- **CS-nose forward contour (open polyline, 3D): a SINGLE arc centered on     C, con** (1 connections) — `backend/geometry/cove_profile.py`
- **Wing-cove forward contour (open polyline, 3D): a single concave arc     centered** (1 connections) — `backend/geometry/cove_profile.py`
- **Normal-foot geometry at one station, in the (a, u) frame local to C.** (1 connections) — `backend/geometry/cove_profile.py`
- **Single-arc mean radius (ADR-003) — the CS nose and wing cove at         this sta** (1 connections) — `backend/geometry/cove_profile.py`
- **Returns (station_feet_cove, station_feet_nose, nose_polygons,     cove_polygons)** (1 connections) — `backend/geometry/te_cut.py`

## Relationships

- [TE Surface Cut Construction](TE_Surface_Cut_Construction.md) (8 shared connections)
- [False Spar Closing Wall](False_Spar_Closing_Wall.md) (6 shared connections)
- [TE Cut Test Fixtures & Tolerances](TE_Cut_Test_Fixtures_%26_Tolerances.md) (4 shared connections)
- [Nose Tangency Validation Test](Nose_Tangency_Validation_Test.md) (3 shared connections)
- [Hinge Frame & Viewer Export](Hinge_Frame_%26_Viewer_Export.md) (3 shared connections)
- [Nose Arc Sampling Test](Nose_Arc_Sampling_Test.md) (2 shared connections)
- [OML Loft Construction](OML_Loft_Construction.md) (2 shared connections)
- [Geometry Module & ADR Map](Geometry_Module_%26_ADR_Map.md) (2 shared connections)
- [Curvature & Tangency Diagnostics](Curvature_%26_Tangency_Diagnostics.md) (2 shared connections)
- [Spar Surfaces & Hardpoints](Spar_Surfaces_%26_Hardpoints.md) (1 shared connections)
- [Reference Geometry & Config Root](Reference_Geometry_%26_Config_Root.md) (1 shared connections)

## Source Files

- `backend/geometry/cove_profile.py`
- `backend/geometry/te_cut.py`

## Audit Trail

- EXTRACTED: 101 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*