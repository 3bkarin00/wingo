


"""NACA 4- and 5-digit airfoil generators (closed-form).

Produces canonical-order points (TE→upper→LE→lower→TE) at cosine x-stations.
Uses the standard OPEN-trailing-edge thickness coefficient (-0.1015 x^4) —
this matches the UIUC-published NACA coordinates (verified in the P1 gate),
which is why the gate can use those .dat files as the published-ordinate
reference. Blunt-TE closure (D6) is applied downstream by resample.close_blunt_te.
"""
from __future__ import annotations

import re

import numpy as np

from backend.airfoils.resample import cosine_x
from backend.airfoils.types import Airfoil, AirfoilFormat

_NACA4_RE = re.compile(r"^naca(\d)(\d)(\d{2})$", re.IGNORECASE)
_NACA5_RE = re.compile(r"^naca(\d)(\d)(\d)(\d{2})$", re.IGNORECASE)

# Standard 5-digit non-reflex mean-line constants (m, k1) keyed by the
# 3-digit camber code, from the NACA 5-digit series definition (Jacobs &
# Pinkerton / Abbott & von Doenhoff). Design Cl for code L is L*0.15; these
# k1 are tabulated for the reference design Cl and scaled linearly otherwise.
_NACA5_MEANLINE = {
    "210": (0.0580, 361.400),
    "220": (0.1260, 51.640),
    "230": (0.2025, 15.957),
    "240": (0.2900, 6.643),
    "250": (0.3910, 3.230),
}


def _thickness(x: np.ndarray, t: float) -> np.ndarray:
    """NACA half-thickness distribution yt(x) for max thickness fraction t
    (open TE)."""
    return 5 * t * (
        0.2969 * np.sqrt(x)
        - 0.1260 * x
        - 0.3516 * x**2
        + 0.2843 * x**3
        - 0.1015 * x**4
    )


def _camber4(x: np.ndarray, m: float, p: float) -> tuple[np.ndarray, np.ndarray]:
    """4-digit camber line yc and slope dyc/dx."""
    yc = np.zeros_like(x)
    dyc = np.zeros_like(x)
    if m == 0.0 or p == 0.0:
        return yc, dyc
    fore = x < p
    aft = ~fore
    yc[fore] = (m / p**2) * (2 * p * x[fore] - x[fore] ** 2)
    dyc[fore] = (2 * m / p**2) * (p - x[fore])
    yc[aft] = (m / (1 - p) ** 2) * ((1 - 2 * p) + 2 * p * x[aft] - x[aft] ** 2)
    dyc[aft] = (2 * m / (1 - p) ** 2) * (p - x[aft])
    return yc, dyc


def _camber5(x: np.ndarray, m: float, k1: float) -> tuple[np.ndarray, np.ndarray]:
    """5-digit non-reflex camber line yc and slope dyc/dx."""
    yc = np.zeros_like(x)
    dyc = np.zeros_like(x)
    fore = x < m
    aft = ~fore
    yc[fore] = (k1 / 6) * (x[fore] ** 3 - 3 * m * x[fore] ** 2 + m**2 * (3 - m) * x[fore])
    dyc[fore] = (k1 / 6) * (3 * x[fore] ** 2 - 6 * m * x[fore] + m**2 * (3 - m))
    yc[aft] = (k1 * m**3 / 6) * (1 - x[aft])
    dyc[aft] = -(k1 * m**3 / 6) * np.ones_like(x[aft])
    return yc, dyc


def _assemble(x: np.ndarray, yc: np.ndarray, dyc: np.ndarray, t: float) -> np.ndarray:
    """Combine camber + thickness into canonical TE→upper→LE→lower→TE points."""
    yt = _thickness(x, t)
    theta = np.arctan(dyc)
    xu = x - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = x + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)
    # x is LE→TE; upper reversed to TE→LE, then lower LE→TE dropping shared LE.
    upper = np.column_stack([xu[::-1], yu[::-1]])
    lower = np.column_stack([xl[1:], yl[1:]])
    return np.vstack([upper, lower])


def generate_naca(name: str, n_points: int = 199) -> Airfoil:
    """Generate a NACA 4- or 5-digit airfoil as a canonical Airfoil.

    Raises ValueError if the name isn't a supported 4/5-digit code (6-series
    and others are out of scope for P1's generator; ingest a .dat instead).
    """
    if n_points % 2 == 0:
        raise ValueError("n_points must be odd (shared LE point)")
    n_per_surface = (n_points + 1) // 2
    x = cosine_x(n_per_surface)  # LE→TE

    m5 = _NACA5_RE.match(name.strip())
    m4 = _NACA4_RE.match(name.strip())
    if m5 and not m4:
        design_cl_digit = int(m5.group(1))
        code = m5.group(1) + m5.group(2) + m5.group(3)
        thickness = int(m5.group(4)) / 100.0
        if code not in _NACA5_MEANLINE:
            raise ValueError(f"unsupported NACA 5-digit camber code '{code}' (reflex/nonstd)")
        m_const, k1 = _NACA5_MEANLINE[code]
        # k1 tabulated for design Cl = 0.3 (code digit 2); scale linearly.
        k1 *= (design_cl_digit * 0.15) / 0.3
        yc, dyc = _camber5(x, m_const, k1)
        source = "naca5"
    elif m4:
        max_camber = int(m4.group(1)) / 100.0
        camber_pos = int(m4.group(2)) / 10.0
        thickness = int(m4.group(3)) / 100.0
        yc, dyc = _camber4(x, max_camber, camber_pos)
        source = "naca4"
    else:
        raise ValueError(f"'{name}' is not a supported NACA 4/5-digit code")

    points = _assemble(x, yc, dyc, thickness)
    return Airfoil(
        name=name.lower(),
        points=points,
        source=source,
        format_detected=AirfoilFormat.GENERATED,
        validation_flags={"generated": True, "n_points": n_points},
    )
