"""Cosine resampling + blunt-TE closure — the shared final stage every
airfoil passes through before placement (docs/conventions.md §airfoils).

Kept free of any tolerance literals: callers pass the target TE thickness
(as a unit-chord fraction) explicitly; the only constant here is the
geometric definition of cosine spacing.
"""
from __future__ import annotations

import numpy as np


def split_surfaces(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Split canonical points (TE→upper→LE→lower→TE) into upper and lower
    surfaces, each returned in ascending-x order (LE→TE) for interpolation.

    The leading edge is the minimum-x point. The upper surface is everything
    from the start (TE) through the LE; the lower is LE through the end (TE).
    """
    le_idx = int(np.argmin(points[:, 0]))
    upper = points[: le_idx + 1][::-1]  # was TE→LE, reverse to LE→TE
    lower = points[le_idx:]  # already LE→TE
    return upper, lower


def _interp_surface(target_x: np.ndarray, surface_le_to_te: np.ndarray) -> np.ndarray:
    """Interpolate a surface's y at target_x. Guards np.interp's requirement
    of strictly-increasing sample x by sorting and de-duplicating (some real
    UIUC foils have a tiny x reversal near TE/LE)."""
    xs = surface_le_to_te[:, 0]
    ys = surface_le_to_te[:, 1]
    order = np.argsort(xs, kind="stable")
    xs, ys = xs[order], ys[order]
    keep = np.concatenate(([True], np.diff(xs) > 0))
    xs, ys = xs[keep], ys[keep]
    return np.interp(target_x, xs, ys)


def cosine_x(n_per_surface: int) -> np.ndarray:
    """n_per_surface cosine-spaced x-stations LE(0)→TE(1); clusters points
    near both LE and TE where curvature is highest."""
    theta = np.linspace(0.0, np.pi, n_per_surface)
    return 0.5 * (1.0 - np.cos(theta))


def cosine_resample(points: np.ndarray, n_total: int) -> np.ndarray:
    """Resample a canonical airfoil to exactly n_total points (must be odd)
    with cosine spacing, preserving canonical TE→upper→LE→lower→TE order.

    With n_total odd, each surface gets (n_total+1)//2 points sharing the LE,
    so 2*k - 1 = n_total.
    """
    if n_total % 2 == 0:
        raise ValueError("n_total must be odd (shared LE point)")
    n_per_surface = (n_total + 1) // 2

    upper, lower = split_surfaces(points)
    xs = cosine_x(n_per_surface)  # LE→TE
    upper_y = _interp_surface(xs, upper)
    lower_y = _interp_surface(xs, lower)

    # Reassemble canonical: upper TE→LE, then lower LE→TE (drop shared LE).
    upper_te_to_le = np.column_stack([xs[::-1], upper_y[::-1]])
    lower_le_to_te = np.column_stack([xs[1:], lower_y[1:]])
    return np.vstack([upper_te_to_le, lower_le_to_te])


def close_blunt_te(points: np.ndarray, te_thickness_frac: float) -> np.ndarray:
    """Ensure the TE gap is at least te_thickness_frac (unit chord), by adding
    a linear thickness wedge (0 at LE, growing to the deficit at TE) split
    symmetrically between upper and lower surfaces (D6 blunt-TE, F-none).

    Never sharpens an already-blunter TE. The wedge keeps the surfaces smooth
    rather than producing a kink only at the endpoint.
    """
    pts = points.copy()
    current_gap = abs(pts[0, 1] - pts[-1, 1])
    if current_gap >= te_thickness_frac:
        return pts

    half_deficit = (te_thickness_frac - current_gap) / 2.0
    le_idx = int(np.argmin(pts[:, 0]))
    x = pts[:, 0]
    # Upper surface = indices [0 .. le_idx]; lower = [le_idx .. end].
    pts[: le_idx + 1, 1] += half_deficit * x[: le_idx + 1]
    pts[le_idx:, 1] -= half_deficit * x[le_idx:]
    return pts
