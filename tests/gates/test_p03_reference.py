"""P3 gate — plan.md §9 pass criteria:

  axis straightness exact by construction (assert 2-point line object);
  containment sampled at >= 50 stations along each axis with margin >= sandwich
  stack — passes on golden AND edge configs (F5); forced rib planes exist at
  every device edge.

"Margin >= sandwich stack" needs the true point-to-surface distance, not just
point-in-solid classification (a point sitting exactly on the skin is
"contained" but has zero clearance — precisely the F5 failure mode). Uses
the real OCP distance-to-shell API confirmed in docs/r0_findings/p03.md
(distance-to-SOLID is always 0 for interior points; must target the shell).
"""
import math
from pathlib import Path

import numpy as np
import pytest
import yaml
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.TopAbs import TopAbs_IN, TopAbs_ON

from backend import tolerances
from backend.geometry.loft import build_oml
from backend.geometry.reference import build_reference_geometry
from backend.geometry.sections import build_planform_sections
from backend.schema.models import Config

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
EDGE_DIR = REPO_ROOT / "tests" / "configs" / "edge"

golden_configs = sorted(GOLDEN_DIR.glob("*.yaml"))
edge_configs = sorted(EDGE_DIR.glob("*.yaml"))
all_configs = golden_configs + edge_configs

CONTAINMENT_SAMPLES = 50  # plan.md §9 P3: ">= 50 stations along each axis"


def _load(path: Path) -> Config:
    return Config.model_validate(yaml.safe_load(path.read_text()))


def _sandwich_stack_mm(config: Config) -> float:
    """core + 2x face-sheet, reusing the same provisional ply-thickness table
    as the P0 validator (backend/schema/validators.py) so the two stay
    consistent."""
    ply_thickness = tolerances.PLY_THICKNESS_MM_PROVISIONAL.get(config.skin.face_sheet.material)
    assert ply_thickness is not None, (
        f"no provisional ply thickness for material '{config.skin.face_sheet.material}' "
        f"(backend/tolerances.py::PLY_THICKNESS_MM_PROVISIONAL)"
    )
    return config.skin.core.thickness_mm + 2 * config.skin.face_sheet.plies * ply_thickness


@pytest.mark.parametrize("cfg_path", all_configs, ids=lambda p: p.stem)
def test_hinge_axis_straightness_and_containment(cfg_path, gate_metrics):
    config = _load(cfg_path)
    sections = build_planform_sections(config)
    oml = build_oml(sections, config.planform.mirror)
    ref = build_reference_geometry(config, sections)

    stack_mm = _sandwich_stack_mm(config)
    oml_shell = oml.Shells()[0].wrapped
    classifier = BRepClass3d_SolidClassifier(oml.wrapped)

    checked = {}
    for name, axis in ref.hinge_axes.items():
        assert axis.geomType() == "LINE", f"{name} axis is not a straight line"

        curve = axis._geomAdaptor()
        u_min, u_max = curve.FirstParameter(), curve.LastParameter()

        worst_margin = math.inf
        for u in np.linspace(u_min, u_max, CONTAINMENT_SAMPLES):
            pnt = curve.Value(u)

            classifier.Perform(pnt, tolerances.KERNEL_TOLERANCE_MM)
            state = classifier.State()
            assert state in (TopAbs_IN, TopAbs_ON), (
                f"{cfg_path.stem}/{name}: axis point "
                f"({pnt.X():.2f}, {pnt.Y():.2f}, {pnt.Z():.2f}) is outside the OML"
            )

            vertex = BRepBuilderAPI_MakeVertex(pnt).Vertex()
            dist_calc = BRepExtrema_DistShapeShape(vertex, oml_shell)
            dist_calc.Perform()
            worst_margin = min(worst_margin, dist_calc.Value())

        assert worst_margin >= stack_mm - tolerances.KERNEL_TOLERANCE_MM, (
            f"{cfg_path.stem}/{name}: min margin {worst_margin:.3f} mm < required "
            f"sandwich stack {stack_mm:.3f} mm (F5 — hinge axis too close to skin)"
        )
        checked[name] = round(worst_margin, 3)

    gate_metrics.setdefault("hinge_axis_margin_mm", {})[cfg_path.stem] = checked
    gate_metrics.setdefault("containment", {})[cfg_path.stem] = True


@pytest.mark.parametrize("cfg_path", all_configs, ids=lambda p: p.stem)
def test_forced_rib_planes_at_device_edges(cfg_path, gate_metrics):
    config = _load(cfg_path)
    sections = build_planform_sections(config)
    ref = build_reference_geometry(config, sections)

    half_span_mm = (
        config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    )

    expected_y = []
    if config.te_surface and config.te_surface.enabled:
        expected_y.append(config.te_surface.span_start_frac * half_span_mm)
        expected_y.append(config.te_surface.span_end_frac * half_span_mm)
    if config.le_droop and config.le_droop.enabled:
        expected_y.append(config.le_droop.span_start_frac * half_span_mm)
        expected_y.append(config.le_droop.span_end_frac * half_span_mm)

    rib_y_coords = [plane.origin.y for plane in ref.rib_planes]
    for y in expected_y:
        found = any(abs(ry - y) < tolerances.KERNEL_TOLERANCE_MM for ry in rib_y_coords)
        assert found, f"{cfg_path.stem}: missing forced rib plane at y={y}"

    gate_metrics.setdefault("forced_ribs", {})[cfg_path.stem] = True
