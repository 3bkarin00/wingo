#!/usr/bin/env python3
"""Export tessellated geometry from the current backend pipeline (P2 OML loft
+ P3 reference geometry + P4 refined per-station device cut) as a single JSON
blob for the standalone diagnostic 3D viewer (tools/viewer/). NOT the planned
product UI (that's P10, React+three.js against the real API) — this is a
throwaway dev tool to see what the backend can build right now.

Usage: .venv/bin/python scripts/export_viewer_data.py [config.yaml ...] [-o out.json]
       (no config args -> exports every tests/configs/devices/te_*.yaml)
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import tolerances
from backend.geometry.loft import build_oml, is_watertight
from backend.geometry.reference import build_reference_geometry
from backend.geometry.sections import build_planform_sections
from backend.schema.models import Config

TESSELLATE_TOLERANCE_MM = 0.5  # visual only — not a physics/gate tolerance
GATE_ARTIFACT_PATH = ROOT / "artifacts" / "gates" / "p04.json"


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


def _load_gate_metrics(stem: str) -> dict | None:
    """Pull this config's ALREADY-VERIFIED numbers straight from the real
    gate artifact (make gate PHASE=p04) rather than re-deriving or, worse,
    hand-typing them into the viewer — the same rule that keeps gates honest
    (never hardcode a geometry result) applies to a demo tool showing them
    off. Returns None if the gate hasn't been run (viewer still works, just
    without the verified-metrics panel)."""
    if not GATE_ARTIFACT_PATH.exists():
        return None
    metrics = json.loads(GATE_ARTIFACT_PATH.read_text())["metrics"]
    if stem not in metrics.get("bodies", {}):
        return None
    return {
        "nose_tangency": metrics["nose_tangency"][stem],
        "nose_is_single_arc": metrics["nose_is_single_arc"][stem],
        "no_unporting_worst_margin_deg": metrics["no_unporting_worst_margin_deg"][stem],
        "cove_clearance_mm": metrics["cove_clearance_mm"][stem],
        "conservation_pct": metrics["conservation_pct"][stem],
        "shards": metrics["shards"][stem],
    }


def _export_one(cfg_path: Path) -> dict:
    from backend.geometry.te_cut import cut_te_surface, hinge_frame

    config = Config.model_validate(yaml.safe_load(cfg_path.read_text()))
    sections = build_planform_sections(config)
    oml = build_oml(sections, config.planform.mirror)
    ref = build_reference_geometry(config, sections)

    assert is_watertight(oml), "OML not watertight — refusing to export broken geometry"

    chord_by_y = {round(s.y_mm, 3): s.chord_mm for s in sections}

    # P4: if the config has a TE control surface (and is a half-wing, so the
    # cut yields 2 bodies), run the real cut and export wing + control surface
    # as separate bodies, plus the hinge point/direction so the viewer can
    # rotate the CS live about the real axis (rather than pre-baking a few
    # fixed deflection snapshots).
    te_cut = None
    if config.te_surface and config.te_surface.enabled and not config.planform.mirror:
        res = cut_te_surface(config, oml)
        p0, _, h, _, _, _ = hinge_frame(config)
        r_vals = [f.R for f in res.stations_nose]
        te_cut = {
            "wing": _tessellate(res.wing),
            "control_surface": _tessellate(res.control_surface),
            "gap_volume_mm3": round(res.gap_volume_mm3, 1),
            "hinge_point": list(p0),
            "hinge_dir": list(h),
            "max_deflection_deg": config.te_surface.max_deflection_deg,
            "overlap_margin_deg": config.te_surface.overlap_margin_deg or tolerances.OVERLAP_MARGIN_DEG,
            "nose_radius_range_mm": [round(min(r_vals), 2), round(max(r_vals), 2)],
            "cove_clearance_target_mm": tolerances.COVE_CLEARANCE_MM,
            "gate_metrics": _load_gate_metrics(cfg_path.stem),
        }

    capabilities = [
        "P2: sections (scale/twist/dihedral/sweep) + watertight OML loft + mirror",
        "P3: spar ruled surfaces, rib planes (auto+forced), hinge axes, hardpoints",
    ]
    if te_cut:
        capabilities.append(
            "P4: single axis-centered nose arc per station (ADR-003) — hinge-axis height "
            "DERIVED by least-squares fit to the true equidistant-from-skin point, tangent "
            "to the skin by construction, 5mm radial cove clearance invariant under rotation, "
            "nose extended past the tangent points to never unport at full deflection"
        )

    return {
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


def main() -> int:
    from backend.schema.errors import ConfigValidationError

    out_path = ROOT / "artifacts" / "viewer_data.json"
    args = list(sys.argv[1:])
    if "-o" in args:
        i = args.index("-o")
        out_path = Path(args[i + 1])
        del args[i:i + 2]

    cfg_paths = [Path(a) for a in args] or sorted((ROOT / "tests/configs/devices").glob("te_*.yaml"))

    configs = {}
    for cfg_path in cfg_paths:
        print(f"exporting {cfg_path.stem} ...")
        try:
            configs[cfg_path.stem] = _export_one(cfg_path)
        except ConfigValidationError as e:
            # Some device configs are DELIBERATE negative test cases
            # (ADR-003, e.g. te_half_twisted.yaml) — correctly rejected by
            # config-time validation, not a viewer bug. Skip, don't crash
            # the whole export batch over an intentional rejection.
            print(f"  SKIPPED (config-time validation rejected it): {e}")

    data = {
        "default_config": "te_half_twisted_moderate" if "te_half_twisted_moderate" in configs else next(iter(configs)),
        "configs": configs,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data))

    for stem, d in configs.items():
        n_tris = len(d["oml"]["triangles"]) + sum(len(s["triangles"]) for s in d["spars"].values())
        if d["te_cut"]:
            n_tris += len(d["te_cut"]["wing"]["triangles"]) + len(d["te_cut"]["control_surface"]["triangles"])
        print(f"  {stem}: {n_tris} triangles, {len(d['rib_planes'])} rib planes, "
              f"{len(d['hinge_axes'])} hinge axes, {len(d['hardpoints'])} hardpoints, "
              f"te_cut={'yes' if d['te_cut'] else 'no'}")
    print(f"wrote {out_path} ({len(configs)} config(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
