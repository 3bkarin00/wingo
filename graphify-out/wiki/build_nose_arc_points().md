# build_nose_arc_points()

> God node · 16 connections · `backend/geometry/cove_profile.py`

**Community:** [Cove/Nose Arc Profile Construction](Cove-Nose_Arc_Profile_Construction.md)

## Connections by Relation

### calls
- build_station_profiles() `EXTRACTED`
- _curvature_check() `EXTRACTED`
- _forward_sweep_angles() `EXTRACTED`
- test_no_unporting() `EXTRACTED`
- test_nose_surface_smoothness() `EXTRACTED`
- _to_3d() `EXTRACTED`
- _overlap_extension_rad() `EXTRACTED`

### contains
- cove_profile.py `EXTRACTED`

### imports
- test_p04_te_cut.py `EXTRACTED`
- te_cut.py `EXTRACTED`
- export_viewer_data.py `EXTRACTED`

### rationale_for
- CS-nose forward contour (open polyline, 3D): a SINGLE arc centered on     C, con `EXTRACTED`

### references
- ADR-003: Single-arc nose + derived hinge-axis height replaces two-arc/Hermite blend `EXTRACTED`
- StationFeet `EXTRACTED`
- ndarray `EXTRACTED`

### shares_data_with
- backend/geometry/cove_profile.py (per-station cove/nose arc profiles) `EXTRACTED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*