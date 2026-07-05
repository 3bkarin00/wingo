"""UIUC .dat ingest: format auto-detect (Selig/Lednicer), normalize to
canonical order, resample + blunt-TE close. Anything that can't be
normalized is QUARANTINED with a reason string — never silently dropped
(P1 gate: 0 silent failures). Detection heuristic is documented and
justified in docs/r0_findings/p01.md.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from backend import tolerances
from backend.airfoils.resample import close_blunt_te, cosine_resample
from backend.airfoils.types import Airfoil, AirfoilFormat, QuarantinedAirfoil


# Format-detection threshold on the first parsed x-value. A Lednicer count is
# an integer point-count (smallest real airfoil block is ~5, and the vendored
# snapshot's smallest is 17). A Selig first coordinate is the trailing edge at
# x≈1.0 — but PUBLISHED data can round it marginally OVER 1.0 (naca23012.dat
# starts at x=1.00003), so a threshold at 1.0 misclassifies. 1.5 sits safely
# in the empty gap between "≈1.0 TE coordinate" and "integer count ≥ 5".
# (Discovered via the P1 smoke test — see docs/r0_findings/p01.md.)
_LEDNICER_COUNT_MIN = 1.5


class _ParseError(Exception):
    """Internal: signals a quarantine with a reason (not a crash)."""


def _parse_pair(line: str) -> tuple[float, float] | None:
    """Parse a line as an (x, y) float pair. Returns None for blank lines;
    raises _ParseError for a non-blank line that isn't two finite floats."""
    s = line.replace("\r", "").strip()
    if not s:
        return None
    parts = s.split()
    if len(parts) < 2:
        raise _ParseError(f"unparseable coordinate line: {s!r}")
    try:
        a, b = float(parts[0]), float(parts[1])
    except ValueError:
        raise _ParseError(f"unparseable coordinate line: {s!r}")
    if not (np.isfinite(a) and np.isfinite(b)):
        raise _ParseError(f"non-finite coordinate: {s!r}")
    return a, b


def detect_format_and_coords(raw_lines: list[str]) -> tuple[AirfoilFormat, np.ndarray]:
    """Return (format, canonical-order raw points). Line 0 is always the
    name/header. Raises _ParseError (→ quarantine) on malformed input."""
    body = raw_lines[1:]

    # Find the first parseable pair to decide the format (r0_findings/p01.md).
    first_idx = None
    first_pair = None
    for i, line in enumerate(body):
        pair = _parse_pair(line)  # may raise → quarantine
        if pair is not None:
            first_idx, first_pair = i, pair
            break
    if first_pair is None:
        raise _ParseError("no parseable coordinate lines found")

    # A first x-value above the count threshold marks a Lednicer count pair;
    # a value near 1.0 is a Selig TE coordinate (see _LEDNICER_COUNT_MIN).
    if first_pair[0] > _LEDNICER_COUNT_MIN:
        n_upper = int(round(first_pair[0]))
        n_lower = int(round(first_pair[1]))
        coords = _collect_pairs(body[first_idx + 1 :])
        if len(coords) < n_upper + n_lower:
            raise _ParseError(
                f"lednicer counts {n_upper}+{n_lower} but only {len(coords)} points found"
            )
        upper = np.array(coords[:n_upper])  # LE→TE
        lower = np.array(coords[n_upper : n_upper + n_lower])  # LE→TE
        # Canonical: upper reversed (TE→LE) + lower dropping shared LE.
        canonical = np.vstack([upper[::-1], lower[1:]])
        return AirfoilFormat.LEDNICER, canonical

    coords = _collect_pairs(body[first_idx:])
    return AirfoilFormat.SELIG, np.array(coords)


def _collect_pairs(lines: list[str]) -> list[tuple[float, float]]:
    out = []
    for line in lines:
        pair = _parse_pair(line)  # raises → quarantine
        if pair is not None:
            out.append(pair)
    return out


def _normalize_unit_chord(points: np.ndarray) -> np.ndarray:
    """Translate LE to x=0 and scale to unit chord, preserving aspect ratio."""
    x_min = float(points[:, 0].min())
    x_max = float(points[:, 0].max())
    chord = x_max - x_min
    if chord <= 0:
        raise _ParseError("degenerate chord (x_max <= x_min)")
    out = points.copy()
    out[:, 0] -= x_min
    return out / chord


def ingest_dat_file(
    path: Path,
    resample_points: int,
    te_thickness_frac: float,
) -> Airfoil | QuarantinedAirfoil:
    raw = Path(path).read_text(errors="replace").splitlines()
    if not raw:
        return QuarantinedAirfoil(path.stem, str(path), "empty file")
    name = raw[0].replace("\r", "").strip() or path.stem
    try:
        fmt, coords = detect_format_and_coords(raw)
        if len(coords) < tolerances.AIRFOIL_MIN_RAW_POINTS:
            raise _ParseError(
                f"too few points ({len(coords)} < {tolerances.AIRFOIL_MIN_RAW_POINTS})"
            )
        coords = _normalize_unit_chord(coords)
        resampled = cosine_resample(coords, resample_points)
        blunt = close_blunt_te(resampled, te_thickness_frac)
        return Airfoil(
            name=path.stem.lower(),
            points=blunt,
            source="uiuc",
            format_detected=fmt,
            validation_flags={
                "display_name": name,
                "raw_point_count": int(len(coords)),
                "resampled_to": resample_points,
            },
        )
    except _ParseError as exc:
        return QuarantinedAirfoil(path.stem, str(path), str(exc))


def ingest_snapshot(
    snapshot_dir: Path,
    resample_points: int,
    te_thickness_frac: float,
) -> tuple[list[Airfoil], list[QuarantinedAirfoil]]:
    """Ingest every .dat in the snapshot. Returns (normalized, quarantined) —
    their union must cover 100% of files (the gate asserts 0 silent losses)."""
    normalized: list[Airfoil] = []
    quarantined: list[QuarantinedAirfoil] = []
    for path in sorted(Path(snapshot_dir).glob("*.dat")):
        result = ingest_dat_file(path, resample_points, te_thickness_frac)
        if isinstance(result, Airfoil):
            normalized.append(result)
        else:
            quarantined.append(result)
    return normalized, quarantined
