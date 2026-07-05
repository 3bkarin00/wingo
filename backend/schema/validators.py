"""P0-scope cross-field config validation rules (see changelog.md 2026-07-05
for the scoping note on which §6 "P0 validation rules" are enforced here vs
deferred to later geometry-dependent gates).

Each function takes the fully-parsed root `Config` and raises
`ConfigValidationError` (with a `ConfigErrorCode`) on violation, or returns
None. Kept out of models.py so field definitions stay uncluttered.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend import tolerances
from backend.airfoils.naca_thickness import min_thickness_mm
from backend.schema.errors import ConfigErrorCode, ConfigValidationError

if TYPE_CHECKING:
    from backend.schema.models import Config, DeviceWindow


def _segment_bounds(config: "Config") -> list[tuple[float, float]]:
    bounds = []
    start = 0.0
    for seg in config.planform.segments:
        bounds.append((start, seg.y_end_frac))
        start = seg.y_end_frac
    return bounds


def _enabled_devices(config: "Config") -> list[tuple[str, "DeviceWindow"]]:
    devices = []
    if config.te_surface is not None and config.te_surface.enabled:
        devices.append(("te_surface", config.te_surface))
    if config.le_droop is not None and config.le_droop.enabled:
        devices.append(("le_droop", config.le_droop))
    return devices


def validate_device_windows(config: "Config") -> None:
    """D4: device windows non-overlapping (TE vs LE) and segment-contained."""
    devices = _enabled_devices(config)

    # Non-overlapping (span-wise) between TE and LE windows.
    if len(devices) == 2:
        (_, a), (_, b) = devices
        if a.span_start_frac < b.span_end_frac and b.span_start_frac < a.span_end_frac:
            raise ConfigValidationError(
                ConfigErrorCode.DEVICE_WINDOW_OVERLAP,
                "te_surface and le_droop span windows overlap "
                f"({a.span_start_frac}-{a.span_end_frac} vs "
                f"{b.span_start_frac}-{b.span_end_frac}); device windows must not overlap (D4)",
            )

    # Segment-contained: each device window must sit fully inside one segment.
    # Segments partition [0, 1] with no gaps, so this is also exactly the
    # "break station outside device windows" rule (§6): a break station is a
    # segment boundary, and a boundary can only fall strictly inside a
    # device's window when that window is NOT contained in a single segment.
    # One check enforces both — a separate break-station check would be
    # unreachable dead code given this equivalence.
    bounds = _segment_bounds(config)
    for name, device in devices:
        contained = any(
            seg_start <= device.span_start_frac and device.span_end_frac <= seg_end
            for seg_start, seg_end in bounds
        )
        if not contained:
            raise ConfigValidationError(
                ConfigErrorCode.DEVICE_NOT_SEGMENT_CONTAINED,
                f"{name} window ({device.span_start_frac}-{device.span_end_frac}) "
                f"is not fully contained within a single segment {bounds} (D4; "
                f"this also covers the break-station-outside-device-window rule)",
            )


def validate_hinge_vs_spar(config: "Config") -> None:
    """TE hinge must be aft of the rear spar (+clearance); LE hinge must be
    forward of the main spar (+clearance). Schema-level xc comparison only —
    real OML containment is P3 (F5)."""
    clearance = tolerances.HINGE_SPAR_XC_CLEARANCE_FRAC
    spars_by_name = {s.name: s for s in config.spars}

    if config.te_surface is not None and config.te_surface.enabled:
        rear = spars_by_name.get("rear")
        if rear is not None:
            min_xc = max(rear.xc_root, rear.xc_tip) + clearance
            for label, hinge_xc in (
                ("hinge_xc_start", config.te_surface.hinge_xc_start),
                ("hinge_xc_end", config.te_surface.hinge_xc_end),
            ):
                if hinge_xc < min_xc:
                    raise ConfigValidationError(
                        ConfigErrorCode.TE_HINGE_TOO_FAR_FORWARD,
                        f"te_surface.{label}={hinge_xc} must be >= rear spar xc "
                        f"({max(rear.xc_root, rear.xc_tip)}) + clearance ({clearance})",
                    )

    if config.le_droop is not None and config.le_droop.enabled:
        main = spars_by_name.get("main")
        if main is not None:
            max_xc = min(main.xc_root, main.xc_tip) - clearance
            for label, hinge_xc in (
                ("hinge_xc_start", config.le_droop.hinge_xc_start),
                ("hinge_xc_end", config.le_droop.hinge_xc_end),
            ):
                if hinge_xc > max_xc:
                    raise ConfigValidationError(
                        ConfigErrorCode.LE_HINGE_TOO_FAR_AFT,
                        f"le_droop.{label}={hinge_xc} must be <= main spar xc "
                        f"({min(main.xc_root, main.xc_tip)}) - clearance ({clearance})",
                    )


def validate_gaps(config: "Config") -> None:
    """gap_mm >= 2x tessellation tolerance and >= 10x kernel tolerance."""
    min_gap = max(
        tolerances.GAP_MIN_TESSELLATION_MULTIPLE * tolerances.TESSELLATION_TOLERANCE_MM,
        tolerances.GAP_MIN_KERNEL_MULTIPLE * tolerances.KERNEL_TOLERANCE_MM,
    )
    for name, device in _enabled_devices(config):
        if device.gap_mm < min_gap:
            raise ConfigValidationError(
                ConfigErrorCode.GAP_BELOW_TOLERANCE,
                f"{name}.gap_mm={device.gap_mm} is below the minimum {min_gap} mm "
                f"(2x tessellation tol / 10x kernel tol)",
            )


def validate_sandwich_stack(config: "Config") -> None:
    """core + 2x face-sheet <= 80% of min local airfoil thickness (F15).

    Skips stations whose airfoil isn't a NACA4/5 code (UIUC/upload airfoils
    need the real P1 ingest pipeline to know their thickness) and skips
    entirely if the face-sheet material isn't in the provisional ply-
    thickness table — both are documented limitations, not silent passes."""
    ply_thickness = tolerances.PLY_THICKNESS_MM_PROVISIONAL.get(config.skin.face_sheet.material)
    if ply_thickness is None:
        return

    face_sheet_mm = config.skin.face_sheet.plies * ply_thickness
    stack_mm = config.skin.core.thickness_mm + 2 * face_sheet_mm

    resolvable = [
        min_thickness_mm(st.airfoil, st.chord_mm) for st in config.planform.stations
    ]
    resolvable = [t for t in resolvable if t is not None]
    if not resolvable:
        return

    min_local_thickness_mm = min(resolvable)
    limit = tolerances.SANDWICH_MARGIN_FRACTION * min_local_thickness_mm
    if stack_mm > limit:
        raise ConfigValidationError(
            ConfigErrorCode.SANDWICH_STACK_EXCEEDS_THICKNESS,
            f"sandwich stack {stack_mm:.3f} mm exceeds {tolerances.SANDWICH_MARGIN_FRACTION * 100:.0f}% "
            f"of min local airfoil thickness ({min_local_thickness_mm:.3f} mm, limit {limit:.3f} mm)",
        )
