#!/usr/bin/env python3
"""Cheap cost probe for kinematics.sweep_min_distance_by_points BEFORE
committing another long gate run to it — two prior approaches
(compound-vs-compound BRepExtrema, then proximity-culled compound-vs-
compound) each burned a full 10-hour pytest-timeout budget on te_half.yaml
(docs/known_issues.md). Reuses the te_cut geometry_cache entry (should be
warm from every prior P8/P7 attempt this session) so this costs seconds,
not the ~8min fixture rebuild.

Prints: vertex count at stride=3, time for ONE angle's full point sweep,
and the extrapolated cost for ~51 coarse angles.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "gates"))


def main() -> int:
    import yaml
    from geometry_cache import get_or_build_shapes

    from backend.geometry.kinematics import sweep_min_distance_by_points
    from backend.geometry.loft import build_oml
    from backend.geometry.sections import build_planform_sections
    from backend.geometry.te_cut import (
        GEOMETRY_SOURCE_FILES as TE_CUT_SOURCE_FILES,
        TeCutRawShapes,
        _station_data,
        build_te_cut_shapes,
        finish_te_cut,
        hinge_frame,
    )
    from backend.schema.models import Config

    cfg_path = ROOT / "tests" / "configs" / "devices" / "te_half.yaml"
    config = Config.model_validate(yaml.safe_load(cfg_path.read_text()))

    sections = build_planform_sections(config, config.airfoils.resample_points)
    oml = build_oml(sections, mirror=config.planform.mirror)

    def _build_raw():
        raw = build_te_cut_shapes(config, oml)
        return [raw.wing_shape, raw.cs_shape]

    (wing_shape, cs_shape), cache_hit = get_or_build_shapes(
        config, TE_CUT_SOURCE_FILES, ["wing_shape", "cs_shape"], _build_raw,
    )
    print(f"te_cut cache hit: {cache_hit}")
    sd = _station_data(config)
    te_raw = TeCutRawShapes(
        wing_shape=wing_shape, cs_shape=cs_shape,
        stations=sd["feet_full"], stations_nose=sd["feet_nose"], hinge_dir=sd["h"],
        oml_volume_mm3=oml.Volume(),
    )
    te_res = finish_te_cut(te_raw)

    p0, _, h, _, _, _ = hinge_frame(config)

    n_verts = len(list(te_res.control_surface.Vertices())[::3])
    print(f"cs_skin vertex count (stride=3): {n_verts}")

    t0 = time.perf_counter()
    one_angle = sweep_min_distance_by_points(
        te_res.control_surface, te_res.wing, p0, h, angles=[0.0],
    )
    one_s = time.perf_counter() - t0
    print(f"ONE angle: {one_s:.2f}s, min_clearance={one_angle.samples[0].min_clearance_mm:.3f}mm")
    print(f"extrapolated 51 angles: ~{one_s * 51 / 60:.1f} min")
    print(f"extrapolated 141 angles: ~{one_s * 141 / 60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
