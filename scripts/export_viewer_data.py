#!/usr/bin/env python3
"""Export tessellated geometry from the current backend pipeline (P2 OML loft
+ P3 reference geometry) as a single JSON blob for the standalone diagnostic
3D viewer (tools/viewer.html). NOT the planned product UI (that's P10,
React+three.js against the real API) — this is a throwaway dev tool to see
what the backend can build right now.

Usage: .venv/bin/python scripts/export_viewer_data.py [config.yaml] [out.json]
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.reference import build_reference_geometry
from backend.geometry.sections import build_planform_sections
from backend.schema.models import Config

TESSELLATE_TOLERANCE_MM = 0.5  # visual only — not a physics/gate tolerance


def _tessellate(shape) -> dict:
    verts, tris = shape.tessellate(TESSELLATE_TOLERANCE_MM)
    return {
        "vertices": [[v.x, v.y, v.z] for v in verts],
        "triangles": [list(t) for t in tris],
    }


def _rib_rectangle(y_mm: float, chord_mm: float) -> list[list[float]]:
    """A generous rectangle in the rib plane (X-Z at fixed Y), sized to the
    local chord so it visually hugs the section rather than floating
    arbitrarily large or small."""
    x0, x1 = -0.15 * chord_mm, 1.15 * chord_mm
    z0, z1 = -0.6 * chord_mm, 0.6 * chord_mm
    return [
        [x0, y_mm, z0], [x1, y_mm, z0], [x1, y_mm, z1], [x0, y_mm, z1],
    ]


def main() -> int:
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "tests/configs/edge/devices_full.yaml"
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "artifacts" / "viewer_data.json"

    config = Config.model_validate(yaml.safe_load(cfg_path.read_text()))
    sections = build_planform_sections(config)
    oml = build_oml(sections, config.planform.mirror)
    ref = build_reference_geometry(config, sections)

    assert is_watertight(oml), "OML not watertight — refusing to export broken geometry"

    # Local chord at each section, for sizing rib rectangles.
    chord_by_y = {round(s.y_mm, 3): s.chord_mm for s in sections}

    # P4: if the config has a TE control surface (and is a half-wing, so the
    # cut yields 2 bodies), run the real cut and export wing + control surface
    # as separate bodies so the gap/cove is visible.
    te_cut = None
    if config.te_surface and config.te_surface.enabled and not config.planform.mirror:
        from backend.geometry.te_cut import cut_te_surface

        res = cut_te_surface(config, oml)
        te_cut = {
            "wing": _tessellate(res.wing),
            "control_surface": _tessellate(res.control_surface),
            "gap_volume_mm3": round(res.gap_volume_mm3, 1),
            "nose_radius_mm": round(res.nose_radius_mm, 2),
            "cove_radius_mm": round(res.cove_radius_mm, 2),
        }

    capabilities = [
        "P2: sections (scale/twist/dihedral/sweep) + watertight OML loft + mirror",
        "P3: spar ruled surfaces, rib planes (auto+forced), hinge axes, hardpoints",
    ]
    if te_cut:
        capabilities.append(
            "P4: TE control-surface cut — 2 watertight bodies, cove/nose clearance, volume conserved"
        )

    data = {
        "config_name": cfg_path.stem,
        "capabilities": capabilities,
        "te_cut": te_cut,
        "half_span_mm": (
            config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
        ),
        "mirror": config.planform.mirror,
        "note": (
            "Reference geometry (spars/ribs/hinges/hardpoints) is built for the "
            "half-span sections P3 actually produces; the OML solid is the "
            "full mirrored span. Not yet mirrored in reference.py."
        ),
        "oml": _tessellate(oml),
        "spars": {name: _tessellate(shell) for name, shell in ref.spar_surfaces.items()},
        "rib_planes": [
            {
                "y_mm": plane.origin.y,
                "corners": _rib_rectangle(
                    plane.origin.y,
                    chord_by_y.get(round(plane.origin.y, 3), sections[-1].chord_mm),
                ),
            }
            for plane in ref.rib_planes
        ],
        "hinge_axes": {
            name: [[v.x, v.y, v.z] for v in (edge.startPoint(), edge.endPoint())]
            for name, edge in ref.hinge_axes.items()
        },
        "hardpoints": [[p.x, p.y, p.z] for p in ref.hardpoints],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data))
    n_tris = len(data["oml"]["triangles"]) + sum(len(s["triangles"]) for s in data["spars"].values())
    print(f"wrote {out_path} — config={cfg_path.stem}, {n_tris} triangles, "
          f"{len(data['rib_planes'])} rib planes, {len(data['hinge_axes'])} hinge axes, "
          f"{len(data['hardpoints'])} hardpoints")
    return 0


if __name__ == "__main__":
    sys.exit(main())
