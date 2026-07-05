"""Core airfoil types shared across the P1 subsystem.

Canonical representation (docs/conventions.md §airfoils): unit chord, point
order TE → upper → LE → lower → TE, blunt TE, cosine-resampled to an odd
count. Every source (NACA generator, UIUC ingest, .dat upload) must produce
this same shape so downstream lofting (P2) is well-defined.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class AirfoilFormat(str, Enum):
    SELIG = "selig"
    LEDNICER = "lednicer"
    GENERATED = "generated"  # NACA closed-form, no source file


@dataclass
class Airfoil:
    """A normalized, canonical-order airfoil."""

    name: str
    points: np.ndarray  # shape (N, 2), canonical order, unit chord
    source: str  # "naca4" | "naca5" | "uiuc" | "dat_upload"
    format_detected: AirfoilFormat
    validation_flags: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.points = np.asarray(self.points, dtype=float)
        if self.points.ndim != 2 or self.points.shape[1] != 2:
            raise ValueError(f"points must be (N, 2), got {self.points.shape}")

    @property
    def n_points(self) -> int:
        return self.points.shape[0]

    def te_thickness(self) -> float:
        """Trailing-edge gap (unit chord) = vertical distance between the
        upper-TE point (first) and lower-TE point (last)."""
        return float(abs(self.points[0, 1] - self.points[-1, 1]))

    def to_list(self) -> list[list[float]]:
        return self.points.tolist()


@dataclass
class QuarantinedAirfoil:
    """A source that could NOT be normalized. Carries a human-readable reason
    — the P1 gate requires 0 silent failures, so every reject is explained."""

    name: str
    source_path: str
    reason: str
