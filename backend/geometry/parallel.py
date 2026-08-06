"""Parallel processing for independent geometry tasks (plan.md Phase 6).

Uses ProcessPoolExecutor for CPU-bound tasks that can run in parallel:
- Airfoil loading: each station's airfoil is independent
- Section placement: each section is independent
- Export formats: STL, glTF, STEP are independent

OCP/CadQuery is NOT thread-safe, so we use processes (not threads) for
geometry operations. The GIL is released during OCP calls anyway, but
ProcessPoolExecutor ensures true parallelism.

Usage:
    from backend.geometry.parallel import parallel_build_sections

    sections = parallel_build_sections(config, max_workers=4)
"""
from __future__ import annotations

import hashlib
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any

import numpy as np

from backend.geometry.airfoil_resolver import resolve_airfoil
from backend.geometry.sections import (
    PlacedSection,
    interp_station,
    le_and_z_offset,
    place_section,
    unit_chord_area,
)
from backend.schema.models import Config


def _build_section_worker(args: tuple) -> dict[str, Any]:
    """Worker function for ProcessPoolExecutor.

    Args:
        args: (config_dict, y_frac, resample_points, te_min_mm, half_span_mm)

    Returns:
        Serialized PlacedSection as dict.
    """
    config_dict, y_frac, resample_points, te_min_mm, half_span_mm = args

    # Reconstruct config from dict
    from backend.schema.models import Config
    config = Config.model_validate(config_dict)

    chord, twist, pts = interp_station(
        config, y_frac, resample_points, te_min_mm
    )
    le_x, z_base = le_and_z_offset(config, y_frac, half_span_mm)
    placed = place_section(
        pts, chord, twist, config.planform.twist_axis_xc,
        y_mm=y_frac * half_span_mm, le_x_mm=le_x, z_base_mm=z_base,
    )
    return PlacedSection(
        y_frac * half_span_mm,
        y_frac,
        chord,
        twist,
        placed,
        unit_chord_area(pts),
    )


def parallel_build_sections(
    config: Config,
    max_workers: int | None = None,
) -> list[PlacedSection]:
    """Build sections in parallel using ProcessPoolExecutor.

    Each section is independent (no shared state), making this a perfect
    candidate for parallelization. For a 61-station wing with 4 workers,
    this can save ~50% of section placement time.

    Args:
        config: validated wing configuration.
        max_workers: number of parallel workers (default: CPU count).

    Returns:
        List of PlacedSection sorted by y_frac.
    """
    if max_workers is None:
        max_workers = min(multiprocessing.cpu_count(), 8)

    # Build list of tasks
    half_span_mm = config.planform.span_mm / 2.0 if config.planform.mirror else config.planform.span_mm
    te_min_mm = config.airfoils.te_min_thickness_mm
    resample_points = config.airfoils.resample_points

    # Section y-fractions: all stations + all interior segment boundaries
    fracs = {s.y_frac for s in config.planform.stations}
    from backend.geometry.sections import _segment_bounds
    for start, end, _, _ in _segment_bounds(config):
        fracs.add(start)
        fracs.add(end)
    fracs = sorted(f for f in fracs if 0.0 <= f <= 1.0)

    # Serialize config once (avoid serializing per-task)
    config_dict = json.loads(config.model_dump_json())

    tasks = [
        (config_dict, f, resample_points, te_min_mm, half_span_mm)
        for f in fracs
    ]

    sections: list[PlacedSection] = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_build_section_worker, task): i
                   for i, task in enumerate(tasks)}
        results = [None] * len(tasks)
        for future in as_completed(futures):
            idx = futures[future]
            results[idx] = future.result()

    # Sort by y_frac (should already be sorted, but ensure)
    sections = sorted(results, key=lambda s: s.y_frac)
    return sections


def parallel_export(
    solid: Any,
    formats: list[str],
    output_dir: str,
    max_workers: int = 4,
) -> dict[str, str]:
    """Export geometry to multiple formats in parallel.

    Args:
        solid: cadquery.Solid to export.
        formats: list of formats (step, stl, gltf).
        output_dir: output directory.
        max_workers: number of parallel workers.

    Returns:
        Dict of format → output file path.
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed

    def _export_worker(args: tuple) -> tuple[str, str]:
        fmt, solid, output_dir = args
        # Each worker exports in its own process (OCP is not thread-safe)
        if fmt == "step":
            path = f"{output_dir}/wing.step"
            solid.exportStep(path)
        elif fmt == "stl":
            path = f"{output_dir}/wing.stl"
            solid.exportStl(path)
        elif fmt == "gltf":
            path = f"{output_dir}/wing.gltf"
            solid.exportGlTF(path)
        else:
            raise ValueError(f"Unknown format: {fmt}")
        return (fmt, path)

    results: dict[str, str] = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_export_worker, (fmt, solid, output_dir)): fmt
                   for fmt in formats}
        for future in as_completed(futures):
            fmt, path = future.result()
            results[fmt] = path

    return results
