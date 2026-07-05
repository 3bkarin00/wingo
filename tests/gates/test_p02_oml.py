"""P2 gate — plan.md §9 pass criteria:

  solid watertight (OCC closed-shell + validity); volume within ±3% of the
  analytic planform × mean-thickness estimate on all golden configs; no
  self-intersection on every edge config (high taper, high twist, thin foil);
  twist verified: rotated section points match hand-computed rotation about the
  declared axis to 1e-6 mm.

Runs the REAL OCP loft kernel (§0.2). Golden expected volumes are committed in
tests/golden/expected/*.json with provenance (§0.2) and act as a regression
tripwire in addition to the plan's ±3% analytic cross-check.
"""
import json
import math
from pathlib import Path

import numpy as np
import pytest
import yaml

from backend.geometry.loft import (
    analytic_volume_estimate,
    build_oml,
    is_watertight,
)
from backend.geometry.sections import build_planform_sections, place_section
from backend.airfoils.naca import generate_naca
from backend.schema.models import Config

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
EDGE_DIR = REPO_ROOT / "tests" / "configs" / "edge"

golden_configs = sorted(GOLDEN_DIR.glob("*.yaml"))
edge_configs = sorted(EDGE_DIR.glob("*.yaml"))

LOFT_VS_ESTIMATE_LIMIT = 0.03  # plan.md §9 P2: ±3%
TWIST_TOL_MM = 1.0e-6  # plan.md §9 P2


def _load(path: Path) -> Config:
    return Config.model_validate(yaml.safe_load(path.read_text()))


@pytest.mark.parametrize("cfg_path", golden_configs, ids=lambda p: p.stem)
def test_golden_watertight_and_volume(cfg_path, gate_metrics):
    config = _load(cfg_path)
    sections = build_planform_sections(config)
    solid = build_oml(sections, config.planform.mirror)

    assert is_watertight(solid), f"{cfg_path.stem}: OML not watertight (valid+closed shell)"

    vol = solid.Volume()
    estimate = analytic_volume_estimate(sections, config.planform.mirror)
    dev = abs(vol - estimate) / estimate
    assert dev < LOFT_VS_ESTIMATE_LIMIT, (
        f"{cfg_path.stem}: loft volume {vol:.0f} deviates {dev*100:.2f}% from "
        f"analytic estimate {estimate:.0f} (limit {LOFT_VS_ESTIMATE_LIMIT*100:.0f}%)"
    )

    # Regression tripwire against the committed golden value (§0.2 provenance).
    expected = json.loads((GOLDEN_DIR / "expected" / f"{cfg_path.stem}.json").read_text())
    exp_vol = expected["expected_volume_mm3"]
    reg = abs(vol - exp_vol) / exp_vol
    assert reg < expected["regression_tolerance_frac"], (
        f"{cfg_path.stem}: loft volume {vol:.0f} drifted {reg*100:.2f}% from committed "
        f"golden {exp_vol:.0f} — deliberate geometry change? regenerate expected/*.json"
    )
    gate_metrics.setdefault("golden", {})[cfg_path.stem] = {
        "volume_mm3": round(vol, 1),
        "estimate_dev_pct": round(dev * 100, 3),
        "regression_dev_pct": round(reg * 100, 3),
        "watertight": True,
    }


@pytest.mark.parametrize("cfg_path", edge_configs, ids=lambda p: p.stem)
def test_edge_no_self_intersection(cfg_path, gate_metrics):
    config = _load(cfg_path)
    sections = build_planform_sections(config)
    solid = build_oml(sections, config.planform.mirror)
    # A self-intersecting loft fails OCC validity; watertight = valid + closed.
    assert is_watertight(solid), (
        f"{cfg_path.stem}: OML invalid/self-intersecting or not watertight"
    )
    gate_metrics.setdefault("edge", {})[cfg_path.stem] = {"watertight": True}


def test_twist_matches_hand_computed_rotation(gate_metrics):
    """Placement's twist must equal an independent rotation about the declared
    twist axis to 1e-6 mm — over a spread of twist angles."""
    canonical = generate_naca("naca2412", 121).points
    chord, twist_axis_xc = 300.0, 0.25
    untwisted = place_section(canonical, chord, 0.0, twist_axis_xc, 0.0, 0.0, 0.0)

    worst = 0.0
    for twist_deg in (-15.0, -5.0, 3.0, 12.0, 25.0):
        placed = place_section(canonical, chord, twist_deg, twist_axis_xc, 0.0, 0.0, 0.0)
        # Independent hand rotation of the untwisted section about the axis point
        # (x = twist_axis_xc*chord on the chord line, z=0) in the X-Z plane.
        xp = twist_axis_xc * chord
        a = math.radians(twist_deg)
        dx = untwisted[:, 0] - xp
        z = untwisted[:, 2]
        x_exp = xp + dx * math.cos(a) - z * math.sin(a)
        z_exp = dx * math.sin(a) + z * math.cos(a)
        dev = max(
            float(np.max(np.abs(placed[:, 0] - x_exp))),
            float(np.max(np.abs(placed[:, 2] - z_exp))),
        )
        worst = max(worst, dev)

    assert worst < TWIST_TOL_MM, f"twist deviates {worst:.2e} mm from hand-computed (limit {TWIST_TOL_MM})"
    gate_metrics["twist_max_dev_mm"] = worst
