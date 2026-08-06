#!/usr/bin/env python3
"""Benchmark harness for WingStructGen.

Measures build time, memory usage, face/edge count, volume, and mesh size
for each benchmark config. Outputs results as JSON for trend tracking.

Usage:
    python benchmarks/run.py                  # run all configs
    python benchmarks/run.py benchmarks/small.yaml  # single config
    python benchmarks/run.py --output results/baseline.json  # custom output
"""
from __future__ import annotations

import argparse
import json
import os
import time
import tracemalloc
from pathlib import Path

import yaml

import cadquery as cq

from backend.schema.models import Config
from backend.geometry.sections import build_planform_sections
from backend.geometry.loft import build_oml, is_watertight, analytic_volume_estimate
from backend.geometry.reference import build_reference_geometry
from backend.geometry.pipeline import build_fast, build_full

REPO_ROOT = Path(__file__).resolve().parent.parent


def _count_faces_edges(solid: cq.Solid) -> tuple[int, int]:
    """Count faces and edges in a solid."""
    return len(solid.Faces()), len(solid.Edges())


def _measure(config_path: Path) -> dict:
    """Run the full pipeline on a config and return metrics."""
    tracemalloc.start()

    config = Config.model_validate(yaml.safe_load(config_path.read_text()))
    half_span = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm

    metrics: dict = {
        "config": config_path.name,
        "stations": len(config.planform.stations),
        "segments": len(config.planform.segments),
        "half_span_mm": half_span,
        "mirror": config.planform.mirror,
        "airfoil_resample_points": config.airfoils.resample_points,
        "has_te_surface": config.te_surface is not None and config.te_surface.enabled,
        "has_le_droop": config.le_droop is not None and config.le_droop.enabled,
        "num_spars": len(config.spars),
        "rib_count": config.ribs.count,
    }

    # Phase 1: Airfoil loading + section placement
    t0 = time.perf_counter()
    tracemalloc.reset_peak()
    sections = build_planform_sections(config)
    dt = (time.perf_counter() - t0) * 1000
    mem = tracemalloc.get_traced_memory()[1] / 1024 / 1024  # MB at peak
    metrics["airfoil_loading_ms"] = round(dt, 1)
    metrics["airfoil_loading_mem_mb"] = round(mem, 2)
    metrics["section_count"] = len(sections)

    # Phase 2: OML loft
    t0 = time.perf_counter()
    tracemalloc.reset_peak()
    solid = build_oml(sections, config.planform.mirror)
    dt = (time.perf_counter() - t0) * 1000
    mem = tracemalloc.get_traced_memory()[1] / 1024 / 1024
    metrics["loft_ms"] = round(dt, 1)
    metrics["loft_mem_mb"] = round(mem, 2)

    # Phase 3: Topology check
    t0 = time.perf_counter()
    watertight = is_watertight(solid)
    dt = (time.perf_counter() - t0) * 1000
    metrics["topology_check_ms"] = round(dt, 1)
    metrics["watertight"] = watertight

    # Phase 4: Volume
    t0 = time.perf_counter()
    vol = solid.Volume()
    estimate = analytic_volume_estimate(sections, config.planform.mirror)
    vol_dev = abs(vol - estimate) / estimate * 100
    dt = (time.perf_counter() - t0) * 1000
    metrics["volume_mm3"] = round(vol, 1)
    metrics["volume_estimate_mm3"] = round(estimate, 1)
    metrics["volume_dev_pct"] = round(vol_dev, 3)
    metrics["volume_ms"] = round(dt, 1)

    # Phase 5: Topology counts
    faces, edges = _count_faces_edges(solid)
    metrics["face_count"] = faces
    metrics["edge_count"] = edges

    # Phase 6: Reference geometry
    t0 = time.perf_counter()
    ref = build_reference_geometry(config, sections)
    dt = (time.perf_counter() - t0) * 1000
    metrics["reference_geometry_ms"] = round(dt, 1)
    metrics["spar_count"] = len(ref.spar_surfaces)
    metrics["rib_plane_count"] = len(ref.rib_planes)
    metrics["hinge_axis_count"] = len(ref.hinge_axes)
    metrics["hardpoint_count"] = len(ref.hardpoints)

    tracemalloc.stop()

    total_ms = sum(v for k, v in metrics.items() if k.endswith("_ms"))
    metrics["total_ms"] = round(total_ms, 1)

    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="WingStructGen benchmark harness")
    parser.add_argument("configs", nargs="*", type=Path,
                        help="Config files to benchmark (default: benchmarks/*.yaml)")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="Output JSON file (default: benchmarks/results/baseline.json)")
    args = parser.parse_args()

    if not args.configs:
        bench_dir = REPO_ROOT / "benchmarks"
        args.configs = sorted(bench_dir.glob("*.yaml"))

    if not args.configs:
        print("No benchmark configs found.", file=__import__("sys").stderr)
        return 1

    results = []
    for cfg_path in args.configs:
        print(f"Running {cfg_path.name} ...")
        m = _measure(cfg_path)
        results.append(m)

        # Also measure fast path
        import time
        t0 = time.perf_counter()
        fast = build_fast(Config.model_validate(yaml.safe_load(cfg_path.read_text())))
        fast_ms = (time.perf_counter() - t0) * 1000
        print(f"  {m['stations']} stations, full={m['total_ms']:.0f}ms, "
              f"fast={fast_ms:.0f}ms, loft={m['loft_ms']:.0f}ms, "
              f"watertight={m['watertight']}, faces={m['face_count']}")

        # Add fast path metrics
        fast_metrics = {
            "config": cfg_path.name + "_fast",
            "stations": m["stations"],
            "segments": m["segments"],
            "half_span_mm": m["half_span_mm"],
            "mirror": m["mirror"],
            "airfoil_resample_points": m["airfoil_resample_points"],
            "has_te_surface": m["has_te_surface"],
            "has_le_droop": m["has_le_droop"],
            "num_spars": m["num_spars"],
            "rib_count": m["rib_count"],
            "airfoil_loading_ms": round(fast.metrics.airfoil_loading_ms, 1),
            "airfoil_loading_mem_mb": 0.0,  # fast path doesn't track mem
            "section_count": fast.metrics.section_count,
            "loft_ms": round(fast.metrics.loft_ms, 1),
            "loft_mem_mb": 0.0,
            "topology_check_ms": 0.0,  # skipped
            "watertight": None,  # skipped
            "volume_mm3": None,  # skipped
            "volume_estimate_mm3": None,
            "volume_dev_pct": None,
            "volume_ms": 0.0,
            "face_count": fast.metrics.face_count,
            "edge_count": fast.metrics.edge_count,
            "reference_geometry_ms": 0.0,  # skipped
            "spar_count": 0,
            "rib_plane_count": 0,
            "hinge_axis_count": 0,
            "hardpoint_count": 0,
            "total_ms": round(fast_ms, 1),
        }
        results.append(fast_metrics)

    output = args.output or REPO_ROOT / "benchmarks" / "results" / "baseline.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2))
    print(f"\nResults written to {output}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
