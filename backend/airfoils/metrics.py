
"""Geometric comparison metrics for airfoils.

Airfoil surfaces are near-vertical at the leading edge, so comparing two
foils by y-at-x badly overstates the difference there (a tiny x-misalignment
maps to a large y gap). Every "do these two curves match" check must instead
use true point-to-curve distance — this module provides it.
"""
from __future__ import annotations

import numpy as np


def max_point_to_curve_deviation(query: np.ndarray, curve: np.ndarray) -> float:
    """Max over `query` points of the minimum Euclidean distance from that
    point to the polyline `curve` (one-directional Hausdorff). Both are (N, 2)
    arrays in the same (unit-chord) coordinate frame; result is in chord units.
    """
    query = np.asarray(query, dtype=float)
    curve = np.asarray(curve, dtype=float)
    a = curve[:-1]
    b = curve[1:]
    ab = b - a
    ab2 = np.sum(ab * ab, axis=1)
    ab2[ab2 == 0] = 1e-30  # guard zero-length segments

    worst = 0.0
    for q in query:
        t = np.clip(np.sum((q - a) * ab, axis=1) / ab2, 0.0, 1.0)
        proj = a + t[:, None] * ab
        worst = max(worst, float(np.min(np.linalg.norm(proj - q, axis=1))))
    return worst
