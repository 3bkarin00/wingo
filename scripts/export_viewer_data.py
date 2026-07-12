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

import numpy as np
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


def _curvature_angle_proxy(pts: np.ndarray) -> np.ndarray:
    """Angle (deg) between consecutive segments at each interior point — the
    exact diagnostic that caught the lumpy-nose defect (docs/r0_findings/
    p04.md): a smooth arc has a small, roughly CONSTANT value; a curvature
    discontinuity shows as a spike. Reimplemented here (not imported from
    tests/gates/test_p04_te_cut.py) to keep this production/dev script from
    depending on test code — same six lines, same formula."""
    d1 = pts[1:-1] - pts[:-2]
    d2 = pts[2:] - pts[1:-1]
    d1n = d1 / np.linalg.norm(d1, axis=1, keepdims=True)
    d2n = d2 / np.linalg.norm(d2, axis=1, keepdims=True)
    cos_a = np.clip(np.sum(d1n * d2n, axis=1), -1.0, 1.0)
    return np.degrees(np.arccos(cos_a))


def _curvature_check(res, a: np.ndarray, u: np.ndarray, max_defl: float, overlap_margin: float) -> dict:
    """Curvature-angle proxy at 5 representative nose stations (root/25%/
    50%/75%/tip of the nose span) — lets the viewer plot the SAME curve that
    diagnosed and confirmed the ADR-003 fix, not just report a pass/fail."""
    from backend.geometry.cove_profile import build_nose_arc_points

    stations = res.stations_nose
    n = len(stations)
    idxs = sorted(set([0, n // 4, n // 2, (3 * n) // 4, n - 1]))
    labels = ["root", "25%", "50%", "75%", "tip"]

    out = []
    for label, i in zip(labels, idxs):
        f = stations[i]
        pts = build_nose_arc_points(f, a, u, max_defl, overlap_margin)
        kink = _curvature_angle_proxy(pts)
        out.append({
            "label": label,
            "kink_deg": [round(float(k), 4) for k in kink],
            "mean_deg": round(float(kink.mean()), 4),
            "spike_ratio": round(float(kink.max() / max(kink.mean(), 1e-9)), 3),
        })
    return {"stations": out}


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


def _sandwich_export(config: Config, sections, res) -> dict:
    """P6 WIP (backend/geometry/iml.py): clean-span-only sandwich shells for
    the wing body — THREE layers per wall (outer face sheet / core / inner
    face sheet), each split into upper/lower per mold half. NOT exported for
    the control surface (its entire extent sits inside/near the TE device
    window, where the offset construction is still known-wrong for the
    cove-arc boundary — see iml.py's module docstring); the wing's own
    te_surface span window carries the same caveat, so the viewer shows the
    window's y-range alongside these layers.

    Every layer is restricted to the actual wing body (booleans against
    res.wing), so the shells DO follow the device cut — the first exported
    version didn't restrict the core band and it visibly sailed through the
    CS pocket, caught in the viewer. In-run assertions below re-verify the
    construction on every export (volume sums over already-computed shapes —
    no extra booleans): zero shards, every kept solid watertight, and the
    upper+lower pair exactly partitioning each of the three rings."""
    import time

    from backend.geometry.booleans import filter_shards
    from backend.geometry.iml import build_sandwich_body, build_sandwich_lofts
    from backend.geometry.loft import is_watertight

    # include_hollow_interior=True: ribs.build_ribs (below) needs the cavity
    # solid. Was False (viewer-shells-only shortcut, skipping the body ∩
    # hollow_IML boolean — among the most expensive operations in iml.py,
    # ~370-670s measured) before ribs existed; the real P6 pipeline always
    # needed it anyway (iml.py's own docstring already said so).
    lofts = build_sandwich_lofts(config, sections)
    wing_sw = build_sandwich_body(res.wing, lofts, include_hollow_interior=True)
    print(f"    sandwich build timings: lofts={lofts.timings_s}, body={wing_sw.timings_s}", flush=True)

    def _checked_volume(label: str, shape) -> float:
        solids, shards = filter_shards(shape)
        assert not shards, f"sandwich {label}: {len(shards)} shard(s) (F3)"
        assert solids, f"sandwich {label}: no solids survived"
        assert all(is_watertight(s) for s in solids), f"sandwich {label}: not watertight"
        return sum(s.Volume() for s in solids)

    vol = {
        label: _checked_volume(label, shape)
        for label, shape in [
            ("face_outer_ring", wing_sw.face_outer_shell),
            ("core_ring", wing_sw.core_shell),
            ("face_inner_ring", wing_sw.face_inner_shell),
            ("face_outer_upper", wing_sw.face_outer_upper),
            ("face_outer_lower", wing_sw.face_outer_lower),
            ("core_upper", wing_sw.core_upper), ("core_lower", wing_sw.core_lower),
            ("face_inner_upper", wing_sw.face_inner_upper),
            ("face_inner_lower", wing_sw.face_inner_lower),
        ]
    }
    for ring, up, lo in [
        ("face_outer_ring", "face_outer_upper", "face_outer_lower"),
        ("core_ring", "core_upper", "core_lower"),
        ("face_inner_ring", "face_inner_upper", "face_inner_lower"),
    ]:
        dev = abs(vol[up] + vol[lo] - vol[ring]) / vol[ring]
        assert dev < 1e-3, (
            f"sandwich {ring}: upper+lower deviates {dev*100:.4f}% from the ring "
            f"({vol[up]:.1f} + {vol[lo]:.1f} vs {vol[ring]:.1f}) — split is not a partition"
        )
    print(f"    sandwich verified: volumes(mm^3)={ {k: round(v, 1) for k, v in vol.items()} } "
          f"(3-ring partition + watertight + no shards)", flush=True)

    # False spar (device-cut closing wall, backend/geometry/false_spar.py) —
    # verified in-run like the shells: no shards, watertight, spans the
    # device window, and clears the moving control surface by at least the
    # cove clearance (its aft face sits at r_cove + standoff from the hinge
    # axis while the CS nose stays within R < r_cove by construction).
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    from backend.geometry.false_spar import build_false_spar
    from backend.geometry.te_cut import hinge_frame as _hinge_frame

    fs = build_false_spar(config, sections, lofts.hollow_iml_solid)
    print(f"    false spar timings: {fs.timings_s}", flush=True)
    vol["false_spar"] = _checked_volume("false_spar", fs.solid)

    p0_fs, p1_fs, _, _, _, _ = _hinge_frame(config)
    bb = fs.solid.BoundingBox()
    y_lo, y_hi = min(p0_fs[1], p1_fs[1]), max(p0_fs[1], p1_fs[1])
    assert bb.ymin <= y_lo + 1.0 and bb.ymax >= y_hi - 1.0, (
        f"false spar does not span the device window: bbox y=[{bb.ymin:.1f}, {bb.ymax:.1f}] "
        f"vs hinge axis y=[{y_lo:.1f}, {y_hi:.1f}]"
    )
    dist_op = BRepExtrema_DistShapeShape(fs.solid.wrapped, res.control_surface.wrapped)
    dist_op.Perform()
    cs_clearance = dist_op.Value()
    assert cs_clearance >= tolerances.COVE_CLEARANCE_MM, (
        f"false spar too close to control surface: {cs_clearance:.2f} mm < "
        f"{tolerances.COVE_CLEARANCE_MM} mm cove clearance"
    )
    print(f"    false spar verified: vol={vol['false_spar']:.1f} mm^3, "
          f"thickness={fs.thickness_mm:.2f} mm, CS clearance={cs_clearance:.2f} mm", flush=True)

    # Ribs (backend/geometry/ribs.py) — verified in-run: every built rib is
    # asserted a single valid watertight solid (build_ribs itself already
    # falls back to a solid slab, or skips the plane entirely, rather than
    # ever hand back something that fails that check — see its module
    # docstring for why both outcomes are expected, not just tolerated).
    from backend.geometry.reference import build_rib_planes
    from backend.geometry.ribs import build_ribs

    t0 = time.perf_counter()
    rib_planes = build_rib_planes(config)
    rib_set = build_ribs(config, wing_sw.hollow_interior, rib_planes)
    ribs_timing_s = time.perf_counter() - t0
    for rib in rib_set.ribs:
        solids, shards = filter_shards(rib.solid, min_volume=1e-6)
        assert len(solids) == 1 and not shards and is_watertight(solids[0]), (
            f"rib at y={rib.y_mm:.1f}: not a single valid watertight solid "
            f"({len(solids)} solids, {len(shards)} shards)"
        )
    print(f"    ribs verified: {ribs_timing_s:.1f}s, {len(rib_set.ribs)}/{len(rib_planes)} built "
          f"({len(rib_set.fallback_solid)} fell back to solid, "
          f"{len(rib_set.skipped_no_section)} skipped at y={rib_set.skipped_no_section}), "
          f"all single/valid/watertight", flush=True)

    t0 = time.perf_counter()
    tess = {
        "wing_face_outer_upper": _tessellate(wing_sw.face_outer_upper),
        "wing_face_outer_lower": _tessellate(wing_sw.face_outer_lower),
        "wing_core_upper": _tessellate(wing_sw.core_upper),
        "wing_core_lower": _tessellate(wing_sw.core_lower),
        "wing_face_inner_upper": _tessellate(wing_sw.face_inner_upper),
        "wing_face_inner_lower": _tessellate(wing_sw.face_inner_lower),
        "wing_false_spar": _tessellate(fs.solid),
    }
    for rib in rib_set.ribs:
        tess[f"wing_rib_{rib.y_mm:.0f}"] = _tessellate(rib.solid)
    print(f"    sandwich tessellation: {time.perf_counter()-t0:.1f}s total, "
          f"{ {k.replace('wing_', ''): len(v['triangles']) for k, v in tess.items()} } tris", flush=True)

    te = config.te_surface
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    tess["device_window_y_mm"] = [
        round(te.span_start_frac * half_span_mm, 1),
        round(te.span_end_frac * half_span_mm, 1),
    ]
    tess["warning"] = (
        "P6 WIP (docs/r0_findings/p06.md): clean-span construction only. "
        "Within device_window_y_mm (the TE hinge region), the wing's real "
        "boundary is the cove arc, not the plain airfoil skin used here — "
        "expect a visible artifact there until the device-region follow-on "
        "lands. Control surface not shown at all (entirely within/near the "
        "device window). Panel is 3 layers per wall (outer face / core / "
        "inner face); where a section is locally thinner than two full "
        "panels (aft ~10% chord near the tip) the walls merge into solid "
        "laminate — expected until ramped drop-offs (D11). Layers split "
        "upper/lower at the camber line (provisional parting; real mold "
        "parting curve lands in P15/P16)."
    )
    return tess


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
    sandwich = None
    if config.te_surface and config.te_surface.enabled and not config.planform.mirror:
        res = cut_te_surface(config, oml)
        p0, _, h, a_dir, u_dir, _ = hinge_frame(config)
        r_vals = [f.R for f in res.stations_nose]
        max_defl = config.te_surface.max_deflection_deg
        overlap_margin = config.te_surface.overlap_margin_deg or tolerances.OVERLAP_MARGIN_DEG
        te_cut = {
            "wing": _tessellate(res.wing),
            "control_surface": _tessellate(res.control_surface),
            "gap_volume_mm3": round(res.gap_volume_mm3, 1),
            "hinge_point": list(p0),
            "hinge_dir": list(h),
            "max_deflection_deg": max_defl,
            "overlap_margin_deg": overlap_margin,
            "nose_radius_range_mm": [round(min(r_vals), 2), round(max(r_vals), 2)],
            "cove_clearance_target_mm": tolerances.COVE_CLEARANCE_MM,
            "gate_metrics": _load_gate_metrics(cfg_path.stem),
            "curvature_check": _curvature_check(res, a_dir, u_dir, max_defl, overlap_margin),
        }
        print(f"    building P6 sandwich shells (clean-span WIP, ~2-3 min of real booleans)...")
        sandwich = _sandwich_export(config, sections, res)

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
    if sandwich:
        capabilities.append(
            "P6 (WIP, clean-span only): 3-layer sandwich shells (outer face / core / inner "
            "face per wall) via 2D per-station offset + loft + subtract (F1: never OCC "
            "shell/thicken) — wrong within the TE device window, see the sandwich panel's warning"
        )

    return {
        "config_name": cfg_path.stem,
        "capabilities": capabilities,
        "te_cut": te_cut,
        "sandwich": sandwich,
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
    rejected = {}
    for cfg_path in cfg_paths:
        print(f"exporting {cfg_path.stem} ...")
        try:
            configs[cfg_path.stem] = _export_one(cfg_path)
        except ConfigValidationError as e:
            # Some device configs are DELIBERATE negative test cases
            # (ADR-003, e.g. te_half_twisted.yaml) — correctly rejected by
            # config-time validation, not a viewer bug. Skip building it,
            # but keep the reason so the viewer can show the fail-fast
            # mechanism actually fired, not just silently omit the config.
            print(f"  SKIPPED (config-time validation rejected it): {e}")
            rejected[cfg_path.stem] = {"code": e.code.value, "message": str(e)}

    data = {
        "default_config": "te_half_twisted_moderate" if "te_half_twisted_moderate" in configs else next(iter(configs)),
        "configs": configs,
        "rejected": rejected,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data))

    for stem, d in configs.items():
        n_tris = len(d["oml"]["triangles"]) + sum(len(s["triangles"]) for s in d["spars"].values())
        if d["te_cut"]:
            n_tris += len(d["te_cut"]["wing"]["triangles"]) + len(d["te_cut"]["control_surface"]["triangles"])
        if d["sandwich"]:
            n_tris += sum(
                len(d["sandwich"][k]["triangles"])
                for k in ("wing_face_outer_upper", "wing_face_outer_lower",
                          "wing_core_upper", "wing_core_lower",
                          "wing_face_inner_upper", "wing_face_inner_lower",
                          "wing_false_spar")
            )
        print(f"  {stem}: {n_tris} triangles, {len(d['rib_planes'])} rib planes, "
              f"{len(d['hinge_axes'])} hinge axes, {len(d['hardpoints'])} hardpoints, "
              f"te_cut={'yes' if d['te_cut'] else 'no'}, sandwich={'yes (WIP)' if d['sandwich'] else 'no'}")
    print(f"wrote {out_path} ({len(configs)} config(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
