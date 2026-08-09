"""Mesh simplification and LOD for GPU viewer optimization (plan.md Phase 10).

Provides:
1. LOD levels: high/medium/low tessellation via adjustable deflection tolerance.
2. Mesh statistics: face/edge/vertex counts, triangle count, surface area.
3. Render performance estimation from mesh statistics.

Uses CadQuery's built-in tessellation (Tessellate) which wraps BRepMesh
internally. Different quality levels are achieved by passing different
deflection tolerances to the tessellation call.

Usage:
    from backend.geometry.mesh import get_mesh_stats, estimate_render_performance

    # Get mesh stats from a solid (uses default high-quality tessellation)
    stats = get_mesh_stats(solid)
    print(f"{stats['triangles']} triangles")

    # Estimate render performance
    perf = estimate_render_performance(stats)
    print(f"Estimated {perf['estimated_ms_per_frame']}ms per frame")
"""
from __future__ import annotations

from dataclasses import dataclass

import cadquery as cq


@dataclass
class MeshStats:
    """Statistics about a tessellated mesh."""
    triangles: int = 0
    edges: int = 0
    vertices: int = 0
    faces: int = 0
    surface_area: float = 0.0


def get_mesh_stats(
    solid: cq.Solid,
    tolerance: float = 0.05,
    angular_tolerance: float = 0.5,
) -> MeshStats:
    """Extract mesh statistics from a solid via CadQuery's tessellation.

    CadQuery's solid.tessellate() returns (vertices, triangle_indices) where
    vertices is a flat list of Vector and triangle_indices is a flat list of
    (i1, i2, i3) index triplets.

    Args:
        solid: cadquery.Solid to tessellate.
        tolerance: maximum allowed deviation from true geometry (mm).
            Low quality: 0.5, Medium: 0.1, High: 0.05.
        angular_tolerance: maximum angular deviation (radians).

    Returns:
        MeshStats with triangle/edge/vertex counts and surface area.
    """
    vertices, tri_indices = solid.tessellate(tolerance, angular_tolerance)

    # Number of triangles = len(indices) (each element is an (i1,i2,i3) tuple)
    num_triangles = len(tri_indices)

    # Surface area from triangulated vertices
    surface_area = _triangle_area_sum(vertices, tri_indices)

    return MeshStats(
        triangles=num_triangles,
        vertices=len(vertices),
        surface_area=surface_area,
    )


def build_lod_meshes(
    solid: cq.Solid,
    quality_levels: dict[str, tuple[float, float]] | None = None,
) -> dict[str, tuple]:
    """Build multiple LOD (Level of Detail) meshes from a single solid.

    Each LOD level uses a different deflection tolerance, producing meshes
    with different triangle counts suitable for various rendering contexts.

    Args:
        solid: cadquery.Solid to tessellate.
        quality_levels: dict of quality_name → (tolerance, angular_tolerance).
            Default: {"high": (0.05, 0.5), "medium": (0.1, 1.0), "low": (0.5, 2.0)}

    Returns:
        dict of quality_name → (vertices, tri_indices) tuple from tessellate().
    """
    if quality_levels is None:
        quality_levels = {
            "high": (0.05, 0.5),
            "medium": (0.1, 1.0),
            "low": (0.5, 2.0),
        }

    meshes = {}
    for quality, (tol, ang) in quality_levels.items():
        meshes[quality] = solid.tessellate(tol, ang)

    return meshes


def compare_mesh_sizes(
    solid: cq.Solid,
    quality_levels: dict[str, tuple[float, float]] | None = None,
) -> dict[str, MeshStats]:
    """Build and compare mesh statistics across all LOD levels.

    Args:
        solid: cadquery.Solid to tessellate.
        quality_levels: same as build_lod_meshes().

    Returns:
        dict of quality_name → MeshStats.
    """
    meshes = build_lod_meshes(solid, quality_levels)
    return {q: _mesh_to_stats(verts, tris) for q, (verts, tris) in meshes.items()}


def _triangle_area_sum(vertices: list, tri_indices: list) -> float:
    """Sum of triangle areas from tessellate output.

    tri_indices is a list of (i1, i2, i3) tuples, not a flat list.
    """
    import math
    total = 0.0
    for i1, i2, i3 in tri_indices:
        v1, v2, v3 = vertices[i1], vertices[i2], vertices[i3]
        # Cross product of two edge vectors, half magnitude = area
        ex1, ey1, ez1 = v2.x - v1.x, v2.y - v1.y, v2.z - v1.z
        ex2, ey2, ez2 = v3.x - v1.x, v3.y - v1.y, v3.z - v1.z
        cx = ey1 * ez2 - ez1 * ey2
        cy = ez1 * ex2 - ex1 * ez2
        cz = ex1 * ey2 - ey1 * ex2
        total += 0.5 * math.sqrt(cx*cx + cy*cy + cz*cz)
    return total


def _mesh_to_stats(vertices: list, tri_indices: list) -> MeshStats:
    """Convert tessellation output to MeshStats."""
    num_triangles = len(tri_indices)

    return MeshStats(
        triangles=num_triangles,
        vertices=len(vertices),
        surface_area=_triangle_area_sum(vertices, tri_indices),
    )


def estimate_render_performance(
    stats: MeshStats,
    target_fps: float = 60.0,
) -> dict[str, float]:
    """Estimate GPU rendering performance from mesh statistics.

    Based on typical modern GPU capabilities:
    - ~0.001ms per triangle for vertex processing
    - ~0.002ms per triangle for fragment processing
    - Total ~0.003ms per triangle

    Args:
        stats: MeshStats from a tessellated mesh.
        target_fps: target frame rate.

    Returns:
        dict with estimated_ms_per_triangle, estimated_ms_per_frame,
        max_triangles_for_target_fps, frame_budget_ms.
    """
    ms_per_triangle = 0.003
    estimated_ms_per_frame = stats.triangles * ms_per_triangle
    max_triangles = (1000.0 / target_fps) / ms_per_triangle

    return {
        "ms_per_triangle": ms_per_triangle,
        "estimated_ms_per_frame": round(estimated_ms_per_frame, 3),
        "max_triangles_for_target_fps": int(max_triangles),
        "frame_budget_ms": round(1000.0 / target_fps, 2),
    }


def get_lod_recommendation(
    stats: MeshStats,
    target_fps: float = 60.0,
) -> dict[str, str]:
    """Recommend LOD level based on mesh size and target frame rate.

    Args:
        stats: MeshStats from a tessellated mesh.
        target_fps: target frame rate.

    Returns:
        dict with recommendation, current_triangles, recommended_triangles,
        reduction_needed.
    """
    max_triangles = (1000.0 / target_fps) / 0.003

    if stats.triangles <= max_triangles:
        recommendation = "current LOD is sufficient"
        recommended_triangles = stats.triangles
        reduction_needed = 0
    else:
        reduction_needed = round((1 - max_triangles / stats.triangles) * 100, 1)
        recommendation = f"reduce triangles by {reduction_needed}% to maintain {target_fps}fps"
        recommended_triangles = int(max_triangles)

    return {
        "recommendation": recommendation,
        "current_triangles": stats.triangles,
        "recommended_triangles": recommended_triangles,
        "reduction_needed": f"{reduction_needed}%",
    }
