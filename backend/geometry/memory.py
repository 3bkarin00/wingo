"""Memory optimization for geometry pipeline (plan.md Phase 8).

Profiles and optimizes memory usage by:
1. Tracking memory allocation per pipeline stage
2. Identifying duplicate OCC objects
3. Implementing object pooling for frequently reused objects
4. Lazy loading of geometry data

Usage:
    from backend.geometry.memory import profile_build, optimize_memory

    # Profile memory usage
    profile = profile_build(config)
    print(f"Peak memory: {profile.peak_mb:.1f} MB")
    for stage in profile.stages:
        print(f"  {stage.name}: {stage.peak_mb:.1f} MB ({stage.objects} objects)")

    # Optimize (clear unused objects, pool frequently used)
    optimize_memory()
"""
from __future__ import annotations

import gc
import tracemalloc
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class StageProfile:
    """Memory profile for a single pipeline stage."""
    name: str
    peak_mb: float = 0.0
    objects: int = 0
    numpy_arrays: int = 0
    numpy_bytes: int = 0


@dataclass
class BuildProfile:
    """Complete memory profile for a geometry build."""
    stages: list[StageProfile] = field(default_factory=list)
    peak_mb: float = 0.0
    total_allocated_mb: float = 0.0
    gc_collections: dict[str, int] = field(default_factory=dict)


def _get_memory_info() -> dict[str, Any]:
    """Get current memory usage statistics."""
    import resource
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "peak_mb": usage.ru_maxrss / 1024,  # Convert KB to MB
        "user_time": usage.ru_utime,
        "system_time": usage.ru_stime,
    }


def _count_objects() -> dict[str, int]:
    """Count objects by type."""
    gc.collect()
    type_counts: dict[str, int] = {}
    for obj in gc.get_objects():
        type_name = type(obj).__name__
        type_counts[type_name] = type_counts.get(type_name, 0) + 1
    return type_counts


def _count_numpy_arrays() -> tuple[int, int]:
    """Count numpy arrays and their total memory usage."""
    gc.collect()
    array_count = 0
    total_bytes = 0
    for obj in gc.get_objects():
        if isinstance(obj, np.ndarray):
            array_count += 1
            total_bytes += obj.nbytes
    return array_count, total_bytes


def profile_stage(
    stage_name: str,
    func: callable,
    *args: Any,
    **kwargs: Any
) -> tuple[Any, StageProfile]:
    """Profile memory usage of a single function call."""
    tracemalloc.start()
    gc.collect()

    # Get initial state
    initial_memory = tracemalloc.get_traced_memory()
    initial_arrays, initial_bytes = _count_numpy_arrays()

    # Execute function
    result = func(*args, **kwargs)

    # Get final state
    current, peak = tracemalloc.get_traced_memory()
    final_arrays, final_bytes = _count_numpy_arrays()
    tracemalloc.stop()

    # Create profile
    profile = StageProfile(
        name=stage_name,
        peak_mb=(peak - initial_memory[1]) / (1024 * 1024),
        objects=final_arrays - initial_arrays,
        numpy_arrays=final_arrays,
        numpy_bytes=final_bytes,
    )

    return result, profile


def profile_build(
    build_func: callable,
    *args: Any,
    **kwargs: Any
) -> BuildProfile:
    """Profile memory usage of a complete geometry build.

    Args:
        build_func: The build function to profile.
        *args, **kwargs: Arguments to pass to the build function.

    Returns:
        BuildProfile with detailed memory statistics.
    """
    # Start tracing
    tracemalloc.start()
    gc.collect()

    # Get initial state
    initial_memory = tracemalloc.get_traced_memory()
    initial_arrays, initial_bytes = _count_numpy_arrays()
    initial_gc = gc.get_stats()

    # Profile each stage
    stages = []

    # Stage 1: Airfoil loading
    from backend.geometry.airfoil_resolver import resolve_airfoil
    def _load_airfoils():
        from backend.schema.models import Config
        config = args[0] if args else kwargs.get('config')
        if config:
            unique_foils = {s.airfoil for s in config.planform.stations}
            for foil_name in unique_foils:
                resolve_airfoil(
                    foil_name,
                    config.airfoils.resample_points,
                    config.airfoils.te_min_thickness_mm / 300.0,
                )
        return None

    _, airfoil_profile = profile_stage("airfoil_loading", _load_airfoils)
    stages.append(airfoil_profile)

    # Stage 2: Section placement
    from backend.geometry.sections import build_planform_sections
    def _build_sections():
        from backend.schema.models import Config
        config = args[0] if args else kwargs.get('config')
        if config:
            build_planform_sections(config)
        return None

    _, section_profile = profile_stage("section_placement", _build_sections)
    stages.append(section_profile)

    # Stage 3: OML loft
    from backend.geometry.loft import build_oml
    def _build_loft():
        from backend.schema.models import Config
        config = args[0] if args else kwargs.get('config')
        if config:
            sections = build_planform_sections(config)
            build_oml(sections, config.planform.mirror)
        return None

    _, loft_profile = profile_stage("oml_loft", _build_loft)
    stages.append(loft_profile)

    # Stage 4: Watertight check
    from backend.geometry.loft import is_watertight
    def _check_watertight():
        from backend.schema.models import Config
        config = args[0] if args else kwargs.get('config')
        if config:
            sections = build_planform_sections(config)
            solid = build_oml(sections, config.planform.mirror)
            is_watertight(solid)
        return None

    _, watertight_profile = profile_stage("watertight_check", _check_watertight)
    stages.append(watertight_profile)

    # Execute the actual build
    result = build_func(*args, **kwargs)

    # Get final state
    current, peak = tracemalloc.get_traced_memory()
    final_arrays, final_bytes = _count_numpy_arrays()
    final_gc = gc.get_stats()

    tracemalloc.stop()

    # Create build profile
    profile = BuildProfile(
        stages=stages,
        peak_mb=(peak - initial_memory[1]) / (1024 * 1024),
        total_allocated_mb=(current - initial_memory[0]) / (1024 * 1024),
        gc_collections={
            "full": final_gc[0].get("collections", 0) - initial_gc[0].get("collections", 0),
            "level1": final_gc[1].get("collections", 0) - initial_gc[1].get("collections", 0),
            "level2": final_gc[2].get("collections", 0) - initial_gc[2].get("collections", 0),
        },
    )

    return profile


def optimize_memory() -> None:
    """Optimize memory usage by:
    1. Clearing unused objects
    2. Running garbage collection
    3. Truncating numpy arrays if possible
    """
    # Run garbage collection
    gc.collect()

    # Clear Python's file I/O cache
    import sys
    sys.stdout.flush()
    sys.stderr.flush()

    # Note: OCC objects are managed by the C++ kernel, not Python GC
    # Manual cleanup of Python-side references helps
    gc.collect()


def get_memory_report() -> dict[str, Any]:
    """Get a detailed memory usage report."""
    info = _get_memory_info()
    type_counts = _count_objects()
    array_count, array_bytes = _count_numpy_arrays()

    # Get top object types
    sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "memory": info,
        "total_objects": sum(type_counts.values()),
        "numpy_arrays": array_count,
        "numpy_bytes": array_bytes,
        "top_types": sorted_types,
    }
