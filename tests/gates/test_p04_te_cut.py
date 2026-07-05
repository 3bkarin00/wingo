"""P4 gate — plan.md §9 pass criteria:

  exactly 2 watertight bodies; vol(wing)+vol(CS)+vol(gap) = vol(P2) within
  0.5%; shard filter reports 0 bodies below min-volume threshold (F3); cove
  clearance angle present (no tangent face pairs, F4).

Runs the REAL OCP boolean kernel on the half-wing device configs
(tests/configs/devices/, mirror:false so the TE cut yields exactly 2 bodies).
The F4 check reads the ACTUAL built cove/nose cylinder radii off the geometry
and asserts they are distinct (concentric-but-not-equal ⇒ non-tangent) — see
docs/r0_findings/p04.md.
"""
from pathlib import Path

import pytest
import yaml

from backend import tolerances
from backend.geometry.booleans import coaxial_cylinder_radii
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.sections import build_planform_sections
from backend.geometry.te_cut import cut_te_surface
from backend.schema.models import Config

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEVICE_DIR = REPO_ROOT / "tests" / "configs" / "devices"
te_configs = sorted(DEVICE_DIR.glob("te_*.yaml"))


def _load(path: Path) -> Config:
    return Config.model_validate(yaml.safe_load(path.read_text()))


@pytest.fixture(scope="module")
def cut_results():
    out = {}
    for path in te_configs:
        config = _load(path)
        oml = build_oml(build_planform_sections(config), config.planform.mirror)
        out[path.stem] = (config, oml, cut_te_surface(config, oml))
    return out


@pytest.mark.parametrize("stem", [p.stem for p in te_configs])
def test_exactly_two_watertight_bodies(stem, cut_results, gate_metrics):
    _, _, res = cut_results[stem]

    # Exactly one real wing body and one real CS body after shard filtering.
    assert res.n_wing_bodies == 1, f"{stem}: expected 1 wing body, got {res.n_wing_bodies}"
    assert res.n_cs_bodies == 1, f"{stem}: expected 1 control-surface body, got {res.n_cs_bodies}"

    assert is_watertight(res.wing), f"{stem}: wing not watertight"
    assert is_watertight(res.control_surface), f"{stem}: control surface not watertight"

    gate_metrics.setdefault("bodies", {})[stem] = {
        "wing_vol_mm3": round(res.wing.Volume(), 1),
        "cs_vol_mm3": round(res.control_surface.Volume(), 1),
    }


@pytest.mark.parametrize("stem", [p.stem for p in te_configs])
def test_volume_conservation(stem, cut_results, gate_metrics):
    _, oml, res = cut_results[stem]
    total = res.wing.Volume() + res.control_surface.Volume() + res.gap_volume_mm3
    dev = abs(total - oml.Volume()) / oml.Volume()
    assert dev < tolerances.DEVICE_CUT_VOLUME_CONSERVATION_FRAC, (
        f"{stem}: vol(wing)+vol(CS)+vol(gap) deviates {dev*100:.3f}% from OML "
        f"(limit {tolerances.DEVICE_CUT_VOLUME_CONSERVATION_FRAC*100:.1f}%)"
    )
    gate_metrics.setdefault("conservation_pct", {})[stem] = round(dev * 100, 4)


@pytest.mark.parametrize("stem", [p.stem for p in te_configs])
def test_no_shards(stem, cut_results, gate_metrics):
    _, _, res = cut_results[stem]
    assert len(res.shards) == 0, (
        f"{stem}: {len(res.shards)} shard(s) below {tolerances.SHARD_MIN_VOLUME_MM3} mm^3 "
        f"survived (F3): {[round(s.Volume(), 3) for s in res.shards]}"
    )
    gate_metrics.setdefault("shards", {})[stem] = len(res.shards)


@pytest.mark.parametrize("stem", [p.stem for p in te_configs])
def test_cove_clearance_no_tangent_faces(stem, cut_results, gate_metrics):
    """F4: the cove (wing) and nose (CS) are coaxial cylinders; if their radii
    matched they'd be tangent/coincident. Assert a real radius gap, read off
    the built geometry (not the input params)."""
    _, _, res = cut_results[stem]
    cove_radii = coaxial_cylinder_radii(res.wing, res.hinge_dir)
    nose_radii = coaxial_cylinder_radii(res.control_surface, res.hinge_dir)

    assert cove_radii, f"{stem}: wing has no coaxial cove cylinder (revolution missing)"
    assert nose_radii, f"{stem}: control surface has no coaxial nose cylinder (revolution missing)"

    # Every wing-cove vs CS-nose pair must be non-tangent (distinct radii).
    for rc in cove_radii:
        for rn in nose_radii:
            assert abs(rc - rn) > tolerances.FACE_TANGENCY_TOLERANCE_MM, (
                f"{stem}: cove radius {rc:.3f} and nose radius {rn:.3f} are tangent "
                f"(within {tolerances.FACE_TANGENCY_TOLERANCE_MM} mm) — F4 clearance missing"
            )
    gate_metrics.setdefault("cove_nose_radii_mm", {})[stem] = {
        "cove": [round(r, 3) for r in cove_radii],
        "nose": [round(r, 3) for r in nose_radii],
    }
